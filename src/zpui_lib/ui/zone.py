from copy import copy

from zpui_lib.ui.canvas import Canvas, MockOutput
from zpui_lib.ui.base_ui import BaseUIElement

from zpui_lib.helpers import setup_logger

logger = setup_logger(__name__, "info")

"""
Zone requirements:
- get values from a callback
- get new zone images from an image-generating callback, passing value to the callback
- only get a new image when the value changes
- cache the images for the values
"""

class Zone(object):
    """
    Allows us to avoid re-generating icons/graphics for different values,
    i.e. if we need to draw a clock, we can use zones to avoid redrawing
    the hours/minutes too often and save some CPU time. Also implements
    caching, so after some time we won't need to redraw, say, seconds -
    just getting the cached image for each of the 60 possible values.
    """
    value = None
    image = None
    prev_value = None

    def __init__(self, value_cb, image_cb, caching = True, i_pass_self = True, \
                 has_canvas=True, v_pass_self = False, trimmable=False, \
                 refresh_every=None, name=None):
        self.value_cb = value_cb
        self.image_cb = image_cb
        self.caching = caching
        self.v_pass_self = v_pass_self
        self.i_pass_self = i_pass_self
        self.trimmable = trimmable
        self.has_canvas = has_canvas
        self.refresh_every = refresh_every
        self.name = name
        self.clear_cache()

    def clear_cache(self):
        if self.caching:
            self.cache = {}

    def set_manager(self, manager):
        self.manager = manager

    def request_refresh(self):
        if hasattr(self, "manager"):
            self.manager.signal_request_refresh(self.name)
        else:
            logger.info("Manager not set (yet?), can't request refresh right now")

    def needs_refresh(self):
        # Getting new value
        if self.v_pass_self:
            new_value = self.value_cb(self)
        else:
            new_value = self.value_cb()
        if new_value != self.value:
            logger.debug("Zone {}: new value {}".format(self.name, new_value))
            # New value!
            self.prev_value = self.value
            self.value = new_value
            return True
        return False

    def set_o_params(self, params):
        """
        This function creates or re-creates the canvas for the zone object to draw onto
        It re-creates the canvas specifically if the zone height changes.
        There's no usecases for that last part yet, it's more of a hunch thing.
        """
        self.o_params = params
        if self.has_canvas:
            if getattr(self, "canvas", None) == None or self.canvas.height != self.o_params["height"]:
                self.canvas = Canvas(MockOutput(**params))
                self.clear_cache()

    def update_image(self):
        # Checking the cache
        if self.caching:
            if self.value in self.cache:
                return self.cache[self.value]
        # Not caching or not found - generating
        if self.i_pass_self:
            image = self.image_cb(self, self.value)
        else:
            image = self.image_cb(self.value)
        # If caching, storing
        if self.caching:
            self.cache[self.value] = copy(image)
        return image

    def get_image(self):
        return self.image

    def refresh(self):
        if self.needs_refresh():
            self.image = self.update_image()
            return True
        return False

class ZoneSpacer(object):
    def __init__(self, value):
        self.value = value

class VerticalZoneSpacer(ZoneSpacer):
    pass

class ZoneManager(object):

    def __init__(self, i, o, markup, zones, name="ZoneManager", **kwargs):
        self.markup = markup
        self.name = name
        self.c = Canvas(o)
        self.o = o
        self.i = i
        self.set_zones(zones)
        #self.refresh_on_start()

    def set_zones(self, zones):
        for name, zone in zones.items():
            zone.max_width = self.o.width
        self.zones = zones
        # giving each zone a reference to this manager
        for name, zone in self.zones.items():
            zone.set_manager(self)
        #self.row_heights = [None for i in range(len(self.markup))]
        self.zones_that_need_refresh = {}
        self.item_widths = []
        self.row_heights = []
        for row in self.markup:
            self.item_widths.append([])
            self.row_heights.append(0)

    def refresh_on_start(self):
        for name, zone in self.zones.items():
            zone.refresh()
            self.zones_that_need_refresh[name] = True

    def signal_request_refresh(self, name=None):
        self.update()
        logger.debug("Update notified from zone {}".format(name))
        self.notify_update(name=name)

    def notify_update(self, name=None):
        #print("Default function call ugh")
        pass

    def get_element_height(self, element):
        if element in self.zones:
            return self.zones[element].get_image().height
        elif isinstance(element, VerticalZoneSpacer):
            return element.value
        return None # I think this path handles "...", but I honestly couldn't tell
        # since this code is from like 2018 =(

    def set_params(self, element):
        if element in self.zones:
            params = {
              "width":self.o.width,
              "height":self.o.height,
              "type":self.o.type,
              "device_mode":self.o.device_mode,
            }
            logger.debug("Setting o params {} for element {}".format(params, element))
            self.zones[element].set_o_params(params)

    def get_element_width(self, element):
        logger.debug("Getting width for element {}".format(element))
        if element in self.zones:
            return self.zones[element].get_image().width
        elif isinstance(element, ZoneSpacer) \
         and not isinstance(element, VerticalZoneSpacer):
            return element.value
        return None # again, explicit None return, mostly for my own sake
        # as I try to figure out how I made "..." handling

    @staticmethod
    def is_dummy_zone(name):
        return all([char == "." for char in name])

    def update(self):
        full_redraw = False
        #self.row_heights = []
        for i, row in enumerate(self.markup):
            # checking for last being a digit denoting height
            row_height = row[-1] if isinstance(row[-1], int) else None
            if row_height: # we got a pre-determined height!
                for item in row:
                    if item == row_height: # useless
                        continue
                    self.set_params(item)
                    if item in self.zones:
                        has_refreshed = self.zones[item].refresh()
                        if has_refreshed and not self.zones_that_need_refresh.get(item, False):
                            self.zones_that_need_refresh[item] = True
                    elif isinstance(item, basestring):
                        if not self.is_dummy_zone(item): # "..." kind of dummy zone
                            logger.warning("Zone {} unknown!".format(item))
                    elif isinstance(item, (ZoneSpacer, VerticalZoneSpacer)):
                        pass
                self.row_heights[i] = row_height
                continue
            # if the row height wasn't set, we determine it by the largest height of the item in row
            for item in row:
                if item in self.zones:
                    zone = self.zones[item]
                    has_refreshed = zone.refresh()
                    if has_refreshed and not self.zones_that_need_refresh.get(item, False):
                        self.zones_that_need_refresh[item] = True
                else:
                    if isinstance(item, basestring):
                        if not self.is_dummy_zone(item): # "..." kind of dummy zone
                            logger.warning("Zone {} unknown!".format(item))
                    elif isinstance(item, (ZoneSpacer, VerticalZoneSpacer)):
                        pass
            # automagic height determination
            item_heights = [self.get_element_height(item) for item in row]
            if list(filter(None, item_heights)):
                row_height = max(filter(None, item_heights))
            else:
                row_height = None
            if row_height != self.row_heights[i]:
                # entire row's height needs to be recalculated because it changed, for some reason
                logger.warning("Row {} height changed from {} to {}!".format(item))
                full_redraw = True
                self.row_heights[i] = row_height
                for item in row:
                    self.set_params(item)
        # Calculating vertical spacing between rows
        empty_row_amount = self.row_heights.count(None)
        if empty_row_amount == 0:
            pass # will just leave empty space at the bottom
        else: # One or more empty rows
            # Let's redistribute the empty space equally
            empty_space = self.o.height-sum(filter(None, self.row_heights))
            # Unless there's no space to redistribute, that is
            if empty_space > 0:
                for i, el in enumerate(self.row_heights):
                    spacing = int(empty_space/empty_row_amount)
                    if el is None:
                        self.row_heights[i] = spacing
        """
        if row_heights != self.row_heights:
            # Row heights changed!
            logger.debug("Row heights changed! {} {}".format(row_heights, self.row_heights))
            self.row_heights = row_heights
            full_redraw = True
        """
        #print(self.item_widths)
        #print(self.row_heights)
        for i, row in enumerate(self.markup):
            #print(row)
            if row and self.row_heights[i] == row[-1]: # last item is row height, filtering out
                item_widths = [self.get_element_width(item) for item in row[:-1]]
            else:
                item_widths = [self.get_element_width(item) for item in row]
            #print(self.markup)
            #print(item_widths, self.item_widths)
            if item_widths != self.item_widths[i]:
                # Item widths changed!
                logger.debug("Item widths changed! Row {}, {} => {}".format(i, self.item_widths[i], item_widths))
                self.item_widths[i] = item_widths
                full_redraw = True
        #print(self.item_widths)
        if full_redraw:
            logger.debug("Doing a full redraw")
            self.c.clear()
        # Redrawing the elements (only those we need to redraw)
        y = 0
        for i, row in enumerate(self.markup):
            x = 0
            row_height = self.row_heights[i]
            item_widths = copy(self.item_widths[i])
            # Calculating horizontal spacing between items
            empty_item_amount = item_widths.count(None)
            if empty_item_amount == 0:
                pass # will just leave empty space on the right
            else: # One or more empty items
                # Let's redistribute the empty space equally
                empty_space = self.o.width-sum(filter(None, item_widths))
                # Unless there's no space to redistribute, that is
                if empty_space > 0:
                    spacing = int(empty_space/empty_item_amount)
                    for k, el in enumerate(item_widths):
                        if el is None:
                            item_widths[k] = spacing
            for j, item in enumerate(row):
                # check for this being the "last row item is height" case
                if j == len(row)-1 and item == row_height:
                    continue # no redraw for the row height number, of course
                width = item_widths[j]
                if item not in self.zones:
                    x += width
                    continue
                if self.zones_that_need_refresh[item] or full_redraw:
                    if full_redraw:
                        logger.debug("Redrawing zone {} because of full redraw".format(item))
                    else:
                        logger.debug("Redrawing zone {} because of update signal".format(item))
                    image = self.zones[item].get_image()
                    self.c.clear((x, y, x+image.width, y+row_height))
                    self.c.paste(image, (x, y))
                    self.zones_that_need_refresh[item] = False
                x += width
            y += row_height

    def get_image(self):
        return self.c.get_image()
