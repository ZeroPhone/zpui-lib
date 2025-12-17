from time import sleep

from zpui_lib.ui.base_ui import BaseUIElement
from zpui_lib.ui.canvas import Canvas, swap_colors, expand_coords
from zpui_lib.ui.funcs import format_for_screen as ffs
from zpui_lib.helpers import setup_logger

logger = setup_logger(__name__, "info")

class DialogBox(BaseUIElement):
    """Implements a dialog box with given values (or some default ones if chosen)."""

    view = None
    value_selected = False
    selected_option = 0
    default_options = {"y":["Yes", True], 'n':["No", False], 'c':["Cancel", None]}
    start_option = 0

    def __init__(self, values, i, o, message="Are you sure?", name="DialogBox", **kwargs):
        """Initialises the DialogBox object.

        Args:

            * ``values``: values to be used. Should be a list of ``[label, returned_value]`` pairs.

              * You can also pass a string "yn" to get "Yes(True), No(False)" options, or "ync" to get "Yes(True), No(False), Cancel(None)" options.
              * Values put together with spaces between them shouldn't be longer than the screen's width.

            * ``i``, ``o``: input&output device objects

        Kwargs:

            * ``message``: Message to be shown on the first line of the screen when UI element is activated
            * ``name``: UI element name which can be used internally and for debugging.

        """
        BaseUIElement.__init__(self, i, o, name, **kwargs)
        if isinstance(values, basestring):
            self.values = []
            for char in values:
                self.values.append(self.default_options[char])
            #value_str = " ".join([value[0] for value in values])
            #assert(len(value_str) <= o.cols, "Resulting string too long for the display!")
        else:
            if not type(values) in (list, tuple):
                raise ValueError("Unsupported 'values' argument - needs a list, supplied {}".format(repr(values)))
            if not values:
                raise ValueError("Empty/invalid 'values' argument!")
            for i, value in enumerate(values):
                if isinstance(value, basestring) and value in self.default_options:
                    #"y", "n" or "c" supplied as a shorthand for one of three default arguments
                    values[i] = self.default_options[value]
            self.values = values
        self.message = message
        self.set_view()
        # Keymap will depend on view
        self.set_default_keymap()

    def set_view(self):
        if "b&w" in self.o.type:
            if self.o.width < 240 or self.o.height < 240:
                view_class = GraphicalView
            else: # screen large enough!
                view_class = FancyGraphicalView
        elif "char" in self.o.type:
            view_class = TextView
        else:
            raise ValueError("Unsupported display type: {}".format(repr(self.o.type)))
        self.view = view_class(self.o, self)

    def set_start_option(self, option_number):
        """
        Allows you to set position of the option that'll be selected upon DialogBox activation.
        """
        self.start_option = option_number

    def before_activate(self):
        self.value_selected = False
        self.selected_option = self.start_option

    @property
    def is_active(self):
        return self.in_foreground

    def get_return_value(self):
        if self.value_selected:
            return self.values[self.selected_option][1]
        else:
            return None

    def idle_loop(self):
        sleep(0.1)

    def generate_keymap(self):
        km = {"KEY_ENTER": 'accept_value'}
        scroll_is_vertical = getattr(self.view, 'scroll_is_vertical', False)
        if scroll_is_vertical:
            km.update({
              "KEY_DOWN": 'move_right',
              "KEY_UP": 'move_left',
              "KEY_LEFT": 'key_deactivate',
            })
        else:
            km.update({
              "KEY_RIGHT": 'move_right',
              "KEY_LEFT": 'move_left',
            })
        return km

    def move_left(self):
        scroll_is_vertical = getattr(self.view, 'scroll_is_vertical', False)
        if self.selected_option == 0:
            if not scroll_is_vertical:
                self.key_deactivate()
            return
        self.selected_option -= 1
        self.refresh()

    def move_right(self):
        if self.selected_option == len(self.values)-1:
            return
        self.selected_option += 1
        self.refresh()

    def accept_value(self):
        self.value_selected = True
        self.key_deactivate()

    def refresh(self):
        self.view.refresh()

    def deactivate(self):
        # if the previous image is present, write it back, to improve UX and avoid consequent dialog boxes writing over each other
        image = getattr(self.view, "previous_image", None)
        if image != None:
            self.o.display_image(image)
        BaseUIElement.deactivate(self)


class TextView(object):

    scroll_is_vertical = False

    def __init__(self, o, el):
        self.o = o
        self.el = el
        self.process_values()

    def process_values(self):
        labels = [label for label, value in self.el.values]
        label_string = " ".join(labels)
        if len(label_string) > self.o.cols:
            raise ValueError("DialogBox {}: all values combined are longer than screen's width".format(self.el.name))
        self.right_offset = (self.o.cols - len(label_string))//2
        self.displayed_label = " "*self.right_offset+label_string
        #Need to go through the string to mark the first places because we need to remember where to put the cursors
        labels = [label for label, value in self.el.values]
        current_position = self.right_offset
        self.positions = []
        for label in labels:
            self.positions.append(current_position)
            current_position += len(label) + 1

    def refresh(self):
        self.o.noCursor()
        self.o.setCursor(1, self.positions[self.el.selected_option])
        self.o.display_data(self.el.message, self.displayed_label)
        self.o.cursor()

class GraphicalView(TextView):

    scroll_is_vertical = True

    char_height = 8
    char_width = 6
    font=None

    def process_values(self):
        self.positions = []
        labels = [label for label, value in self.el.values]
        for label in labels:
            label_width = len(label)*self.char_width
            label_start = (self.o.width - label_width)//2
            if label_start < 0: label_start = 0
            self.positions.append(label_start)

    def get_image(self):
        c = Canvas(self.o)
        #Drawing text
        chunk_y = 0
        cols = self.o.cols
        formatted_message = ffs(self.el.message, self.o.cols)
        if len(formatted_message)*(self.char_height+2) > self.o.height - self.char_height - 2:
            raise ValueError("DialogBox {}: message is too long to fit on the screen: {}".format(self.el.name, formatted_message))
        for line in formatted_message:
            c.text(line, (0, chunk_y), font=self.font)
            chunk_y += self.char_height + 2
        first_label_y = chunk_y
        for i, value in enumerate(self.el.values):
            label = value[0]
            label_start = self.positions[i]
            c.text(label, (label_start, chunk_y), font=self.font)
            chunk_y += self.char_height + 2

        #Calculating the cursor dimensions
        first_char_x = self.positions[self.el.selected_option]
        option_length = len( self.el.values[self.el.selected_option][0] ) * self.char_width
        c_x1 = first_char_x - 2
        c_x2 = c_x1 + option_length + 2
        c_y1 = first_label_y + self.el.selected_option*(2 + self.char_height)
        c_y2 = c_y1 + self.char_height
        #Some readability adjustments
        cursor_dims = ( c_x1, c_y1, c_x2 + 2, c_y2 + 2 )

        #Drawing the cursor
        cursor_image = c.get_image(coords=cursor_dims)
        # inverting colors - background to foreground and vice-versa
        cursor_image = swap_colors(cursor_image, c.default_color, c.background_color, c.background_color, c.default_color)
        c.paste(cursor_image, coords=cursor_dims[:2])
        return c.get_image()

    def refresh(self):
        self.o.display_image(self.get_image())

class pt16GraphicalView(GraphicalView):

    scroll_is_vertical = True

    char_height = 16
    char_width = 8
    font = ("Fixedsys62.ttf", char_height)

class FancyGraphicalView(GraphicalView):

    scroll_is_vertical = False

    char_height = 16
    char_width = 8
    font = ("Fixedsys62.ttf", char_height)

    previous_image = None
    first_run = True

    box_height_mul = 1.4
    box_width_mul = 1.2
    clear_mul = 0.025 # 5% of canvas height/width,  since it's applied to both sides

    def get_image(self):
        c = Canvas(self.o)
        # only save image on first run
        if self.o.current_image or self.previous_image:
            # maybe TODO next time get a previous-context image? todo allow that if the image is from the "main" context?
            if self.first_run:
                #print("Saving previous image")
                self.previous_image = self.o.current_image
                self.first_run = False
            #if self.previous_image != None:
            c.paste(self.previous_image, (0, 0))
        else:
            if getattr(self.el, "context", None):
                context = self.el.context
                self.previous_image = context.get_previous_context_image()
                if self.previous_image:
                    c.paste(self.previous_image, (0, 0))

        # shamelessly reusing code from the simpler graphicalview
        text_height = 0
        cols = (self.o.width)//self.char_width
        formatted_message = ffs(self.el.message, cols)
        max_len = max([len(m) for m in formatted_message])
        text_width = max_len*self.char_width
        # this checks if the text overfills the textbox vertically, but I don't wanna deal with it for this view just yet
        #if len(formatted_message)*(char_height+2) > self.o.height - char_height - 2:
        #    raise ValueError("DialogBox {}: message is too long to fit on the screen: {}".format(self.el.name, formatted_message))
        for line in formatted_message:
            text_height += self.char_height + 2

        labels_height = int(self.char_height * 1.5)
        labels_width = 0
        # pre-calculating width of all labels
        for i, value in enumerate(self.el.values):
            label = value[0]
            label_start = self.positions[i]
            labels_width += len(label) * self.char_width

        # now, calculate the outer box dimensions
        box_width_og = max(text_width, labels_width)
        box_width = int(box_width_og * self.box_width_mul)
        box_height_og = text_height + labels_height
        box_height = int(box_height_og * self.box_height_mul)
        box_coords = c.center_box(box_width, box_height, return_four=True)
        e_coords = int(c.width*self.clear_mul), int(c.height*self.clear_mul), int(c.width*self.clear_mul), int(c.height*self.clear_mul)
        clear_coords = expand_coords(box_coords, e_coords)
        c.clear(clear_coords)
        c.rectangle(box_coords)
        # actually drawing text
        top_x, top_y = box_coords[:2]
        padding_y = int((box_height-box_height_og)//3)
        total_padding_x = int(box_width-box_width_og)
        text_y = top_y + padding_y
        for line in formatted_message:
            text_width = len(line)*self.char_width
            x = top_x + box_width - text_width
            c.text(line, (x, text_y), font=self.font)
            text_y += self.char_height
        # actually drawing labels
        label_y = top_y + box_height - (labels_height+padding_y)
        x = top_x + box_width - text_width
        label_padding_x = int(total_padding_x // (len(self.el.values)+1))
        label_start = top_x + box_width - labels_width - ((len(self.el.values)+1)*label_padding_x)
        for i, value in enumerate(self.el.values):
            label = value[0]
            label_width = len(label)*self.char_width
            if i == self.el.selected_option:
                c.text(label, (label_start, label_y), font=self.font)
                cursor_dims = (label_start, label_y, label_start+label_width, label_y + self.char_height)
                #cursor_dims = (label_start-1, label_y-1, label_start+label_width+2, label_y + self.char_height+2)
                # Drawing the cursor
                cursor_image = c.get_image(coords=cursor_dims)
                # inverting colors - background to foreground and vice-versa
                cursor_image = swap_colors(cursor_image, c.default_color, c.background_color, c.background_color, c.default_color)
                c.paste(cursor_image, coords=cursor_dims[:2])
            else:
                c.rectangle_wh((label_start-1, label_y-1, label_width+2, self.char_height+2),)
                c.text(label, (label_start, label_y), font=self.font)
            label_start += label_width + label_padding_x

        return c.get_image()
