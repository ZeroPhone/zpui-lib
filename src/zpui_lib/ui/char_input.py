from time import sleep
import string

from zpui_lib.ui.utils import to_be_foreground
from zpui_lib.ui.canvas import Canvas, swap_colors
from zpui_lib.ui.base_ui import BaseUIElement
from zpui_lib.helpers import setup_logger
logger = setup_logger(__name__, "warning")


class CharArrowKeysInput(BaseUIElement):
    """
    Implements a character input dialog which allows to input a character string using arrow keys to scroll through characters
    """

    chars = string.ascii_lowercase
    Chars = string.ascii_uppercase
    numbers = '0123456789'
    hexadecimals = '0123456789ABCDEF'
    specials = "!\"#$%&'()[]<>*+,-./:;=?^_|"
    space = ' '
    backspace = chr(0x08)

    mapping = {
    '][c':chars,
    '][C':Chars,
    '][n':numbers,
    '][S':space,
    '][b':backspace,
    '][h':hexadecimals,
    '][s':specials}

    in_foreground = False
    value = []
    position = 0
    cancel_flag = False
    charmap = ""

    def __init__(self, i, o, message="Value:", value="",  allowed_chars=['][S', '][c', '][C', '][s', '][n'], name="CharArrowKeysInput", initial_value=""):
        """Initialises the CharArrowKeysInput object.

        Args:

            * ``i``, ``o``: input&output device objects

        Kwargs:

            * ``value``: Value to be edited. If not set, will start with an empty string.
            * ``allowed_chars``: Characters to be used during input. Is a list of strings designating ranges which can be the following:

              * '][c' for lowercase ASCII characters
              * '][C' for uppercase ASCII characters
              * '][s' for special characters
              * '][S' for space
              * '][n' for numbers
              * '][h' for hexadecimal characters (0-F)

              If a string does not designate a range of characters, it'll be added to character map as-is.

            * ``message``: Message to be shown in the first row of the display
            * ``name``: UI element name which can be used internally and for debugging.

        """
        BaseUIElement.__init__(self, i, o, name)
        self.message = message
        self.allowed_chars = allowed_chars
        self.allowed_chars.append("][b") #Adding backspace by default
        self.generate_charmap()
        #Support for obsolete attribute
        if not value and initial_value:
            value = initial_value
        if type(value) != str:
            raise ValueError("CharArrowKeysInput needs a string!")
        self.value = list(value)
        self.char_indices = [] #Fixes a bug with char_indices remaining from previous input ( 0_0 )
        for char in self.value:
            self.char_indices.append(self.charmap.index(char))
        self.set_view()

    def set_view(self):
        if "b&w" in self.o.type:
            view_class = GraphicalView
        elif "char" in self.o.type:
            view_class = TextView
        else:
            raise ValueError("Unsupported display type: {}".format(repr(self.o.type)))
        self.view = view_class(self.o, self)

    def get_return_value(self):
        if self.cancel_flag:
            return None
        else:
            return ''.join(self.value) #Making string from the list we have

    def idle_loop(self):
        sleep(0.1)

    @property
    def is_active(self):
        return self.in_foreground

    def print_value(self):
        """ A debug method. Useful for hooking up to an input event so that you can see current value. """
        logger.info(self.value)

    @to_be_foreground
    def move_up(self):
        """Changes the current character to the next character in the charmap"""
        while len(self.char_indices) <= self.position:
            self.char_indices.append(0)
            self.value.append(self.charmap[0])

        char_index = self.char_indices[self.position]
        if char_index >= (len(self.charmap)-1):
            char_index = 0
        else:
            char_index += 1
        self.char_indices[self.position] = char_index
        self.value[self.position] = self.charmap[char_index]
        self.refresh()

    @to_be_foreground
    def move_down(self):
        """Changes the current character to the previous character in the charmap"""
        while len(self.char_indices) <= self.position:
            self.char_indices.append(0)
            self.value.append(self.charmap[0])
        char_index = self.char_indices[self.position]
        if char_index == 0:
            char_index = len(self.charmap) - 1
        else:
            char_index -= 1
        self.char_indices[self.position] = char_index
        self.value[self.position] = self.charmap[char_index]
        self.refresh()

    @to_be_foreground
    def move_right(self):
        """Moves cursor to the next element. """
        self.check_for_backspace()
        self.position += 1
        if self.view.last_displayed_char < self.position: #Went too far to the part of the value that isn't currently displayed
            self.view.last_displayed_char = self.position
            self.view.first_displayed_char = self.position - self.o.cols
        self.refresh()

    @to_be_foreground
    def move_left(self):
        """Moves cursor to the previous element. If first element is chosen, exits and makes the element return None."""
        self.check_for_backspace()
        if self.position == 0:
            self.exit()
            return
        self.position -= 1
        if self.view.first_displayed_char > self.position: #Went too far back to the part that's not currently displayed
            self.view.first_displayed_char = self.position
            self.view.last_displayed_char = self.position + self.o.cols
        self.refresh()

    @to_be_foreground
    def accept_value(self):
        """Selects the currently active number value, making activate() return it."""
        self.check_for_backspace()
        logger.debug("Value accepted")
        self.deactivate()

    @to_be_foreground
    def exit(self):
        """Exits discarding all the changes to the value."""
        logger.debug("{} exited without changes".format(self.name))
        self.cancel_flag = True
        self.deactivate()

    def generate_keymap(self):
        return {
        "KEY_RIGHT": 'move_right',
        "KEY_UP": 'move_up',
        "KEY_DOWN": 'move_down',
        "KEY_LEFT": 'move_left',
        "KEY_ENTER": 'accept_value'
        }

    def generate_charmap(self):
        for value in self.allowed_chars:
            if value in self.mapping.keys():
                self.charmap += self.mapping[value]
            else:
                self.charmap += value

    def check_for_backspace(self):
        for i, char_value in enumerate(self.value):
            if char_value == self.backspace:
                self.value.pop(i)
                self.char_indices.pop(i)

    @to_be_foreground
    def refresh(self):
        self.view.refresh()
        logger.debug("{}: refreshed data on display".format(self.name))


class TextView(object):

    last_displayed_char = 0
    first_displayed_char = 0

    def __init__(self, o, el):
        self.o = o
        self.el = el
        self.last_displayed_char = self.o.cols

    def get_displayed_data(self):
        """
        Formats the value and the message to show it on the screen,
        then returns a list that can be directly used by o.display_data.
        Uses HD44780-specific characters.
        """
        if self.first_displayed_char >= len(self.el.value): #Value is off-screen
            value = ""
        else:
            value = ''.join(self.el.value)[self.first_displayed_char:][:self.o.cols]
        return [self.el.message, value]

    def convert_chars_to_hd44780_charset(self, message, value):
        value = value.replace(self.el.backspace, chr(0x7f))
        value = value.replace(' ', chr(255)) #Displaying all spaces as black boxes
        return message, value

    def refresh(self):
        self.o.noCursor()
        #self.o.cursor()# Only needed for testing TextView on luma.oled
        displayed_data = self.convert_chars_to_hd44780_charset( *self.get_displayed_data() )
        self.o.display_data(*displayed_data)
        self.o.cursor()


class GraphicalView(TextView):

    def get_image(self):
        c = Canvas(self.o)

        # Getting displayed data, drawing it
        lines = self.get_displayed_data()
        for i, line in enumerate(lines):
            y = (i*self.o.char_height - 1) if i != 0 else 0
            c.text(line, (2, y))

        # Calculating the cursor dimensions
        c_x1 = (self.el.position-self.first_displayed_char) * self.o.char_width
        c_x2 = c_x1 + self.o.char_width
        c_y1 = self.o.char_height * 1 # second line
        c_y2 = c_y1 + self.o.char_height

        # Some readability adjustments
        cursor_dims = ( c_x1, c_y1, c_x2 + 2, c_y2 + 1 )

        # Drawing the cursor
        cursor_image = c.get_image(coords=cursor_dims)
        cursor_image = swap_colors(cursor_image, c.default_color, c.background_color, c.background_color, c.default_color)
        c.paste(cursor_image, coords=cursor_dims[:2])
        #c.invert_rect(cursor_dims)

        return c.get_image()

    def refresh(self):
        self.o.display_image(self.get_image())
