from zpui_lib.helpers import setup_logger, BackgroundRunner

logger = setup_logger(__name__, "info")

# some consts
# flags that zpui_cli will use in the LoadApp call
FLAG_APP_UNLOAD = 1 << 0
FLAG_APP_LOAD = 1 << 1
FLAG_APP_DEBUG = 1 << 2

# flags that will be returned as part of AppLoadReply
RETURN_LOAD_SUCCESS = 0
RETURN_LOAD_NOTFOUND = 1 << 0
RETURN_LOAD_EXCEPTION = 1 << 1
# extra flags that tell at which stage the app load failed
RETURN_UNLOAD_FAILED = 1 << 8
RETURN_LOAD_FAILED = 1 << 9

RETURN_NOTIFY_SUCCESS = 0
RETURN_NOTIFY_FAIL_DESERIALIZE = 1 << 0
RETURN_NOTIFY_FAIL_NOPROVIDER = 1 << 1

api_host = "127.0.0.1"
api_port = 50058

# thread for API runner
api_runner_br = None

rpc_available = False

try:
    import asyncio
    #from grpclib.utils import graceful_exit
    from grpclib.server import Server, Stream
    from zpui_lib.helpers.grpc_files.zpui_api_grpc import LoaderBase, NotifyReceiverBase
    from zpui_lib.helpers.grpc_files.zpui_api_pb2 import AppLoadRequest, AppLoadReply, NotifyData, NotifyReply
except:
    logger.exception("RPC API load fail! This might require installing additional libraries manually.")
else:
    rpc_available = True
    logger.info("RPC API loaded!")

if rpc_available:

    class Loader(LoaderBase):
        app_man = None
        def set_app_manager(self, app_man):
            self.app_man = app_man

        async def LoadApp(self, stream: Stream[AppLoadRequest, AppLoadReply]) -> None:
            request = await stream.recv_message()
            assert request is not None
            message = f'App load request: {request.path}, params: {request.parameters}!'
            logger.debug(message)
            ret, info = self.app_man.api_load_app(request.path, request.parameters)
            await stream.send_message(AppLoadReply(result=ret, info=info))

    class NotifyReceiver(NotifyReceiverBase):
        context_manager = None
        def set_context_manager(self, context_manager):
            self.context_manager = context_manager

        async def Send(self, stream: Stream[NotifyData, NotifyReply]) -> None:
            request = await stream.recv_message()
            assert request is not None
            message = f'Notify data: {request.data}, params: {request.parameters}!'
            logger.debug(message)
            ret, info = self.context_manager.api_forward_notify(request.data, request.parameters)
            await stream.send_message(NotifyReply(result=ret, info=info))

    async def api_runner(app_manager, context_manager):
        global loader, server, notify_receiver
        loader = Loader()
        notify_receiver = NotifyReceiver()
        loader.set_app_manager(app_manager)
        notify_receiver.set_context_manager(context_manager)
        server = Server([loader, notify_receiver])
        #with graceful_exit([server]):
        await server.start(api_host, api_port)
        logger.info(f'API serving on {api_host}:{api_port}')
        await server.wait_closed()

    def start_api_thread(app_manager, context_manager):
        global api_runner_br
        if not api_runner_br or api_runner_br.finished:
            api_runner_br = BackgroundRunner(lambda: asyncio.run(api_runner(app_manager, context_manager)))
            api_runner_br.run()
        else:
            logger.error("API BackgroundRunner already present!")
