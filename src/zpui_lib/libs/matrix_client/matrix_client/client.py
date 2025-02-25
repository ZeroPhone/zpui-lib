# -*- coding: utf-8 -*-
# Copyright 2015 OpenMarket Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from .api import MatrixHttpApi
from .checks import check_user_id
from .errors import MatrixRequestError, MatrixUnexpectedResponse
from .room import Room
from .user import User
try:
    from .crypto.olm_device import OlmDevice
    ENCRYPTION_SUPPORT = True
except ImportError:
    import traceback; traceback.print_exc()
    ENCRYPTION_SUPPORT = False
from threading import Thread
from time import sleep
from uuid import uuid4
from warnings import warn
import logging
import sys

logger = logging.getLogger(__name__)


# Cache constants used when instantiating Matrix Client to specify level of caching
class CACHE(int):
    pass


CACHE.NONE = CACHE(-1)
CACHE.SOME = CACHE(0)
CACHE.ALL = CACHE(1)
# TODO: rather than having CACHE.NONE as kwarg to MatrixClient, there should be a separate
# LightweightMatrixClient that only implements global listeners and doesn't hook into
# User, Room, etc. classes at all.


class MatrixClient:
    """
    The client API for Matrix. For the raw HTTP calls, see MatrixHttpApi.

    Args:
        base_url (str): The url of the HS preceding /_matrix.
            e.g. (ex: https://localhost:8008 )
        token (Optional[str]): If you have an access token
            supply it here.
        user_id (Optional[str]): Optional. Obsolete. For backward compatibility.
        valid_cert_check (bool): Check the homeservers
            certificate on connections?
        cache_level (CACHE): One of CACHE.NONE, CACHE.SOME, or
            CACHE.ALL (defined in module namespace).
        encryption (bool): Optional. Whether or not to enable end-to-end encryption
            support.
        encryption_conf (dict): Optional. Configuration parameters for encryption.
            Refer to :func:`~matrix_client.crypto.olm_device.OlmDevice` for supported
            options, since it will be passed to this class.
        restore_device_id (bool): Optional. Only valid when encryption is enabled. When
            turned on, the device ID corresponding to the user ID will be retrieved from
            the encryption database, if it exists.
        verify_devices (bool): Optional. When enabled, sending a message will fail when
            there are unknown devices in an encrypted room. A client will have to
            inspect those, and resend its message. Note that this can be configured later
            on a per room basis.

    Returns:
        `MatrixClient`

    Raises:
        `MatrixRequestError`, `ValueError`

    Examples:

        Create a new user and send a message::

            client = MatrixClient("https://matrix.org")
            token = client.register_with_password(username="foobar",
                password="monkey")
            room = client.create_room("myroom")
            room.send_image(file_like_object)

        Send a message with an already logged in user::

            client = MatrixClient("https://matrix.org", token="foobar",
                user_id="@foobar:matrix.org")
            client.add_listener(func)  # NB: event stream callback
            client.rooms[0].add_listener(func)  # NB: callbacks just for this room.
            room = client.join_room("#matrix:matrix.org")
            response = room.send_text("Hello!")
            response = room.kick("@bob:matrix.org")

        Incoming event callbacks (scopes)::

            def user_callback(user, incoming_event):
                pass

            def room_callback(room, incoming_event):
                pass

            def global_callback(incoming_event):
                pass

    Attributes:
        users (dict): A map from user ID to :class:`.User` object.
            It is populated automatically while tracking the membership in rooms, and
            shouldn't be modified directly.
            A :class:`.User` object in this dict is shared between all :class:`.Room`
            objects where the corresponding user is joined.
    """

    def __init__(self, base_url, token=None, user_id=None,
                 valid_cert_check=True, sync_filter_limit=20,
                 cache_level=CACHE.ALL, encryption=False, encryption_conf=None,
                 restore_device_id=False, verify_devices=False):
        if user_id:
            warn(
                "user_id is deprecated. "
                "Now it is requested from the server.", DeprecationWarning
            )

        if encryption and not ENCRYPTION_SUPPORT:
            raise ValueError("Failed to enable encryption. Please make sure the olm "
                             "library is available.")
        if restore_device_id and not encryption:
            raise ValueError("restore_device_id only makes sense when encryption is "
                             "enabled.")
        if encryption and cache_level != CACHE.ALL:
            raise ValueError("Encryption is unvailable on cache_level other than "
                             "CACHE.ALL.")

        self.api = MatrixHttpApi(base_url, token)
        self.api.validate_certificate(valid_cert_check)
        self.listeners = []
        self.presence_listeners = {}
        self.invite_listeners = []
        self.left_listeners = []
        self.ephemeral_listeners = []
        self.device_id = None
        self._encryption = encryption
        self.encryption_conf = encryption_conf or {}
        self.olm_device = None
        self.first_sync = True
        self.restore_device_id = restore_device_id
        self.verify_devices = verify_devices
        if isinstance(cache_level, CACHE):
            self._cache_level = cache_level
        else:
            self._cache_level = CACHE.ALL
            raise ValueError(
                "cache_level must be one of CACHE.NONE, CACHE.SOME, CACHE.ALL"
            )

        self.sync_token = None
        self.sync_filter = '{ "room": { "timeline" : { "limit" : %i } } }' \
            % sync_filter_limit
        self.sync_thread = None
        self.should_listen = False

        """ Time to wait before attempting a /sync request after failing."""
        self.bad_sync_timeout_limit = 60 * 60
        self.rooms = {
            # room_id: Room
        }
        self.users = {
            # user_id: User
        }
        if token:
            response = self.api.whoami()
            self.user_id = response["user_id"]
            self._sync()

    def get_sync_token(self):
        warn("get_sync_token is deprecated. Directly access MatrixClient.sync_token.",
             DeprecationWarning)
        return self.sync_token

    def set_sync_token(self, token):
        warn("set_sync_token is deprecated. Directly access MatrixClient.sync_token.",
             DeprecationWarning)
        self.sync_token = token

    def set_user_id(self, user_id):
        warn("set_user_id is deprecated. Directly access MatrixClient.user_id.",
             DeprecationWarning)
        self.user_id = user_id

    # TODO: combine register methods into single register method controlled by kwargs
    def register_as_guest(self):
        """ Register a guest account on this HS.
        Note: HS must have guest registration enabled.
        Returns:
            str: Access Token
        Raises:
            MatrixRequestError
        """
        response = self.api.register(kind='guest')
        return self._post_registration(response)

    def register_with_password(self, username, password):
        """ Register for a new account on this HS.

        Args:
            username (str): Account username
            password (str): Account password

        Returns:
            str: Access Token

        Raises:
            MatrixRequestError
        """
        response = self.api.register(
            {
                "auth": {"type": "m.login.dummy"},
                "username": username,
                "password": password
            }
        )
        return self._post_registration(response)

    def _post_registration(self, response):
        self.user_id = response["user_id"]
        self.token = response["access_token"]
        self.hs = response["home_server"]
        self.api.token = self.token
        self._sync()
        return self.token

    def login_with_password_no_sync(self, username, password):
        """Deprecated. Use ``login`` with ``sync=False``.

        Login to the homeserver.

        Args:
            username (str): Account username
            password (str): Account password

        Returns:
            str: Access token

        Raises:
            MatrixRequestError
        """
        warn("login_with_password_no_sync is deprecated. Use login with sync=False.",
             DeprecationWarning)
        return self.login(username, password, sync=False)

    def login_with_password(self, username, password, limit=10):
        """Deprecated. Use ``login`` with ``sync=True``.

        Login to the homeserver.

        Args:
            username (str): Account username
            password (str): Account password
            limit (int): Deprecated. How many messages to return when syncing.
                This will be replaced by a filter API in a later release.

        Returns:
            str: Access token

        Raises:
            MatrixRequestError
        """
        warn("login_with_password is deprecated. Use login with sync=True.",
             DeprecationWarning)
        return self.login(username, password, limit, sync=True)

    def login(self, username, password, limit=10, sync=True, device_id=None):
        """Login to the homeserver.

        Args:
            username (str): Account username
            password (str): Account password
            limit (int): Deprecated. How many messages to return when syncing.
                This will be replaced by a filter API in a later release.
            sync (bool): Optional. Whether to initiate a /sync request after logging in.
            device_id (str): Optional. ID of the client device. If it is not specified,
                the server will auto-generate one, or it may be retrieved
                from database if ``restore_device_id`` is ``True``. If it is specified,
                and ``restore_device_id`` is ``True``, the eventual encryption keys stored
                along with a previous device ID of the current user are discarded.

        Returns:
            str: Access token

        Raises:
            MatrixRequestError
        """
        if not device_id and self.restore_device_id:
            try:
                check_user_id(username)
            except ValueError:
                raise ValueError("When using restore_device_id, a full user ID "
                                 "must be supplied when logging in.")
            try:
                self.olm_device = OlmDevice(
                    self.api, username, **self.encryption_conf)
                device_id = self.olm_device.device_id
                logger.info('Device ID was sucessfully retrieved from database.')
            except ValueError:
                pass

        response = self.api.login(
            "m.login.password", user=username, password=password, device_id=device_id
        )
        self.user_id = response["user_id"]
        self.token = response["access_token"]
        self.hs = response["home_server"]
        self.api.token = self.token
        self.device_id = response["device_id"]

        if self._encryption:
            if not self.olm_device:
                self.olm_device = OlmDevice(
                    self.api, self.user_id, self.device_id, **self.encryption_conf)
            self.olm_device.upload_identity_keys()
            self.olm_device.upload_one_time_keys()

        if sync:
            """ Limit Filter """
            self.sync_filter = '{ "room": { "timeline" : { "limit" : %i } } }' % limit
            self._sync()
        return self.token

    def logout(self):
        """ Logout from the homeserver.
        """
        self.stop_listener_thread()
        self.api.logout()

    # TODO: move room creation/joining to User class for future application service usage
    # NOTE: we may want to leave thin wrappers here for convenience
    def create_room(self, alias=None, is_public=False, invitees=None):
        """ Create a new room on the homeserver.

        Args:
            alias (str): The canonical_alias of the room.
            is_public (bool):  The public/private visibility of the room.
            invitees (str[]): A set of user ids to invite into the room.

        Returns:
            Room

        Raises:
            MatrixRequestError
        """
        response = self.api.create_room(alias, is_public, invitees)
        return self._mkroom(response["room_id"])

    def join_room(self, room_id_or_alias):
        """ Join a room.

        Args:
            room_id_or_alias (str): Room ID or an alias.

        Returns:
            Room

        Raises:
            MatrixRequestError
        """
        response = self.api.join_room(room_id_or_alias)
        room_id = (
            response["room_id"] if "room_id" in response else room_id_or_alias
        )
        return self._mkroom(room_id)

    def get_rooms(self):
        """ Return a dict of {room_id: Room objects} that the user has joined.

        Returns:
            Room{}: Rooms the user has joined.
        """
        warn("get_rooms is deprecated. Directly access MatrixClient.rooms.",
             DeprecationWarning)
        return self.rooms

    # TODO: create Listener class and push as much of this logic there as possible
    # NOTE: listeners related to things in rooms should be attached to Room objects
    def add_listener(self, callback, event_type=None):
        """ Add a listener that will send a callback when the client recieves
        an event.

        Args:
            callback (func(roomchunk)): Callback called when an event arrives.
            event_type (str): The event_type to filter for.

        Returns:
            uuid.UUID: Unique id of the listener, can be used to identify the listener.
        """
        listener_uid = uuid4()
        # TODO: listeners should be stored in dict and accessed/deleted directly. Add
        # convenience method such that MatrixClient.listeners.new(Listener(...)) performs
        # MatrixClient.listeners[uuid4()] = Listener(...)
        self.listeners.append(
            {
                'uid': listener_uid,
                'callback': callback,
                'event_type': event_type
            }
        )
        return listener_uid

    def remove_listener(self, uid):
        """ Remove listener with given uid.

        Args:
            uuid.UUID: Unique id of the listener to remove.
        """
        self.listeners[:] = (listener for listener in self.listeners
                             if listener['uid'] != uid)

    def add_presence_listener(self, callback):
        """ Add a presence listener that will send a callback when the client receives
        a presence update.

        Args:
            callback (func(roomchunk)): Callback called when a presence update arrives.

        Returns:
            uuid.UUID: Unique id of the listener, can be used to identify the listener.
        """
        listener_uid = uuid4()
        self.presence_listeners[listener_uid] = callback
        return listener_uid

    def remove_presence_listener(self, uid):
        """ Remove presence listener with given uid

        Args:
            uuid.UUID: Unique id of the listener to remove
        """
        self.presence_listeners.pop(uid)

    def add_ephemeral_listener(self, callback, event_type=None):
        """ Add an ephemeral listener that will send a callback when the client recieves
        an ephemeral event.

        Args:
            callback (func(roomchunk)): Callback called when an ephemeral event arrives.
            event_type (str): The event_type to filter for.

        Returns:
            uuid.UUID: Unique id of the listener, can be used to identify the listener.
        """
        listener_id = uuid4()
        self.ephemeral_listeners.append(
            {
                'uid': listener_id,
                'callback': callback,
                'event_type': event_type
            }
        )
        return listener_id

    def remove_ephemeral_listener(self, uid):
        """ Remove ephemeral listener with given uid.

        Args:
            uuid.UUID: Unique id of the listener to remove.
        """
        self.ephemeral_listeners[:] = (listener for listener in self.ephemeral_listeners
                                       if listener['uid'] != uid)

    def add_invite_listener(self, callback):
        """ Add a listener that will send a callback when the client receives
        an invite.

        Args:
            callback (func(room_id, state)): Callback called when an invite arrives.
        """
        self.invite_listeners.append(callback)

    def add_leave_listener(self, callback):
        """ Add a listener that will send a callback when the client has left a room.

        Args:
            callback (func(room_id, room)): Callback called when the client
            has left a room.
        """
        self.left_listeners.append(callback)

    def add_key_request_listener(self, callback):
        """Add a listener that will send a callback when a device requests keys.

        NOTE:
            This can only be used after logging in.

        NOTE:
            Only one listener can exist, and calling this method a second time will
            discard the first one.

        Args:
            callback (func(dict, func(list))): Callback called when key requests arrive.
                It is given a map from device ID to :class:`.Device` object, which
                corresponds to the devices requesting keys. This map should be used to
                verify devices if relevant. The callback then needs to call the function
                it was given as second argument with a list of the device IDs whose key
                requests should be answered. Key requests from other devices will be
                discarded.
        """
        self.olm_device.key_sharing_manager.key_request_callback = callback

    def add_key_forward_listener(self, callback):
        """Add a listener that will send a callback when we receive a key.

        When a listener exists, keys are requested automatically each time we are unable
        to decrypt a Megolm event due to missing keys.
        A client could maintain a map from the ``session_id`` property of a
        ``m.room.encrypted`` event to a list of corresponding events, and use this
        method to be notified when it can try to decrypt them again.

        NOTE:
            This can only be used after logging in. Since keys are not requested when a
            listener doesn't exist, a client wanting to requests keys on start-up should
            login with ``sync=False``, then add a listener, and then sync.

        NOTE:
            Only one listener can exist, and calling this method a second time will
            discard the first one.

        Args:
            callback (func(string)): Callback called when a forwarded key arrive.
                It is given a Megolm session ID.
        """
        self.olm_device.key_sharing_manager.key_forward_callback = callback

    def listen_for_events(self, timeout_ms=30000):
        """
        This function just calls _sync()

        In a future version of this sdk, this function will be deprecated and
        _sync method will be renamed sync with the intention of it being called
        by downstream code.

        Args:
            timeout_ms (int): How long to poll the Home Server for before
               retrying.
        """
        # TODO: see docstring
        self._sync(timeout_ms)

    def listen_forever(self, timeout_ms=30000, exception_handler=None,
                       bad_sync_timeout=5):
        """ Keep listening for events forever.

        Args:
            timeout_ms (int): How long to poll the Home Server for before
               retrying.
            exception_handler (func(exception)): Optional exception handler
               function which can be used to handle exceptions in the caller
               thread.
            bad_sync_timeout (int): Base time to wait after an error before
                retrying. Will be increased according to exponential backoff.
        """
        _bad_sync_timeout = bad_sync_timeout
        self.should_listen = True
        while (self.should_listen):
            try:
                self._sync(timeout_ms)
                _bad_sync_timeout = bad_sync_timeout
            # TODO: we should also handle MatrixHttpLibError for retry in case no response
            except MatrixRequestError as e:
                logger.warning("A MatrixRequestError occured during sync.")
                if e.code >= 500:
                    logger.warning("Problem occured serverside. Waiting %i seconds",
                                   bad_sync_timeout)
                    sleep(bad_sync_timeout)
                    _bad_sync_timeout = min(_bad_sync_timeout * 2,
                                            self.bad_sync_timeout_limit)
                elif exception_handler is not None:
                    exception_handler(e)
                else:
                    raise
            except Exception as e:
                logger.exception("Exception thrown during sync")
                if exception_handler is not None:
                    exception_handler(e)
                else:
                    raise

    def start_listener_thread(self, timeout_ms=30000, exception_handler=None):
        """ Start a listener thread to listen for events in the background.

        Args:
            timeout (int): How long to poll the Home Server for before
               retrying.
            exception_handler (func(exception)): Optional exception handler
               function which can be used to handle exceptions in the caller
               thread.
        """
        try:
            thread = Thread(target=self.listen_forever,
                            args=(timeout_ms, exception_handler))
            thread.daemon = True
            self.sync_thread = thread
            self.should_listen = True
            thread.start()
        except RuntimeError:
            e = sys.exc_info()[0]
            logger.error("Error: unable to start thread. %s", str(e))

    def stop_listener_thread(self):
        """ Stop listener thread running in the background
        """
        if self.sync_thread:
            self.should_listen = False
            self.sync_thread.join()
            self.sync_thread = None

    # TODO: move to User class. Consider creating lightweight Media class.
    def upload(self, content, content_type, filename=''):
        """ Upload content to the home server and recieve a MXC url.

        Args:
            content (bytes): The data of the content.
            content_type (str): The mimetype of the content.
            filename (str): Optional. The filename of the content.

        Raises:
            MatrixUnexpectedResponse: If the homeserver gave a strange response
            MatrixRequestError: If the upload failed for some reason.
        """
        try:
            response = self.api.media_upload(content, content_type, filename=filename)
            if "content_uri" in response:
                return response["content_uri"]
            else:
                raise MatrixUnexpectedResponse(
                    "The upload was successful, but content_uri wasn't found."
                )
        except MatrixRequestError as e:
            raise MatrixRequestError(
                code=e.code,
                content="Upload failed: %s" % e
            )

    def _mkroom(self, room_id):
        room = Room(self, room_id, verify_devices=self.verify_devices)
        if self._encryption:
            try:
                event = self.api.get_state_event(room_id, "m.room.encryption")
                if event["algorithm"] == "m.megolm.v1.aes-sha2":
                    room.encrypted = True
            except MatrixRequestError as e:
                if e.code != 404:
                    raise
        self.rooms[room_id] = room
        return self.rooms[room_id]

    # TODO better handling of the blocking I/O caused by update_one_time_key_counts
    def _sync(self, timeout_ms=30000):
        response = self.api.sync(self.sync_token, timeout_ms, filter=self.sync_filter)

        if self._encryption and 'device_lists' in response:
            if response['device_lists'].get('changed'):
                self.olm_device.device_list.update_user_device_keys(
                    response['device_lists']['changed'], self.sync_token)
            if response['device_lists'].get('left'):
                self.olm_device.device_list.stop_tracking_users(
                    response['device_lists']['left'])

        self.sync_token = response["next_batch"]

        if self._encryption and self.first_sync:
            self.first_sync = False
            self.olm_device.device_list.update_after_restart(self.sync_token)

        for presence_update in response['presence']['events']:
            for callback in self.presence_listeners.values():
                callback(presence_update)

        for room_id, invite_room in response['rooms']['invite'].items():
            for listener in self.invite_listeners:
                listener(room_id, invite_room['invite_state'])

        for room_id, left_room in response['rooms']['leave'].items():
            for listener in self.left_listeners:
                listener(room_id, left_room)
            if room_id in self.rooms:
                del self.rooms[room_id]

        if 'to_device' in response:
            for event in response['to_device']['events']:
                if self._encryption:
                    if event['type'] == 'm.room.encrypted':
                        self.olm_device.olm_handle_encrypted_event(event)
                    elif event['type'] == 'm.room_key_request':
                        self.olm_device.key_sharing_manager.handle_key_request(event)
        if self._encryption:
            self.olm_device.key_sharing_manager.trigger_key_requests_callback()

        if self._encryption and 'device_one_time_keys_count' in response:
            self.olm_device.update_one_time_key_counts(
                response['device_one_time_keys_count'])

        for room_id, sync_room in response['rooms']['join'].items():
            if room_id not in self.rooms:
                self._mkroom(room_id)
            room = self.rooms[room_id]
            # TODO: the rest of this for loop should be in room object method
            room.prev_batch = sync_room["timeline"]["prev_batch"]

            for event in sync_room["state"]["events"]:
                event['room_id'] = room_id
                room._process_state_event(event)

            for event in sync_room["timeline"]["events"]:
                event['room_id'] = room_id
                room._put_event(event)

                # TODO: global listeners can still exist but work by each
                # room.listeners[uuid] having reference to global listener

                # Dispatch for client (global) listeners
                for listener in self.listeners:
                    if (
                        listener['event_type'] is None or
                        listener['event_type'] == event['type']
                    ):
                        listener['callback'](event)

            if self._encryption and room.encrypted:
                # Track the new users in the room
                self.olm_device.device_list.track_pending_users()

            for event in sync_room['ephemeral']['events']:
                event['room_id'] = room_id
                room._put_ephemeral_event(event)

                for listener in self.ephemeral_listeners:
                    if (
                        listener['event_type'] is None or
                        listener['event_type'] == event['type']
                    ):
                        listener['callback'](event)

    def get_user(self, user_id):
        """Deprecated. Return a User by their id.

        This method only instantiate a User, which should be done directly.
        You can also use :attr:`users` in order to access a User object which
        was created automatically.

        Args:
            user_id (str): The matrix user id of a user.
        """
        warn("get_user is deprecated. Directly instantiate a User instead.",
             DeprecationWarning)
        return User(self, user_id)

    # TODO: move to Room class
    def remove_room_alias(self, room_alias):
        """Remove mapping of an alias

        Args:
            room_alias(str): The alias to be removed.

        Returns:
            bool: True if the alias is removed, False otherwise.
        """
        try:
            self.api.remove_room_alias(room_alias)
            return True
        except MatrixRequestError:
            return False

    def get_fingerprint(self):
        """Get the fingerprint of the current device.

        This is used when verifying devices.
        """
        if not self._encryption:
            raise ValueError("Encryption is not enabled, this device has no fingerprint.")
        return self.olm_device.ed25519

    def export_keys(self, outfile, passphrase):
        """Export all the Megolm decryption keys of this device.

        The keys will be encrypted using the passphrase.

        NOTE:
            This does not save other information such as the private identity keys
            of the device.

        Args:
            outfile (str): The file to write the keys to.
            passphrase (str): The encryption passphrase.
        """
        if not self._encryption:
            raise ValueError("Encryption is not enabled, there are no keys to export.")
        self.olm_device.export_keys(outfile, passphrase)

    def import_keys(self, infile, passphrase):
        """Import Megolm decryption keys.

        The keys will be added to the current instance as well as written to database.

        Args:
            infile (str): The file containing the keys.
            passphrase (str): The decryption passphrase.
        """
        if not self._encryption:
            raise ValueError("Encryption is not enabled, cannot import keys.")
        self.olm_device.import_keys(infile, passphrase)
