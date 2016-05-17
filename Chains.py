import sublime
import sublime_plugin
import calendar
import datetime
import itertools

NOT_FOUND = sublime.Region(-1, -1)
DONE_SYMBOL = 'X'
NORMAL_SYMBOL = ' '
WEEKEND_SYMBOL = '.'
TODAY_KEY = 'today'
INITIAL_MESSAGE = ("<Put your goal here that you want to achieve everyday. "
                   "Remember, DON'T BREAK THE CHAIN>")

"""A dict(month_name, month_int) with right adjust leading space and
a trailing space. This to be used for regex purposes."""
MONTHS = {m:("{month}: "
            .format(month=calendar.month_name[m].rjust(10, ' ')))
                 for m in range(1, 13)}


def dbtc():
    """output the calendar of current year in text with month
    follow by days on each row"""
    current_yr = datetime.date.today().year
    CALENDAR_WIDTH = 158

    init_msg = "** {0} **".format(INITIAL_MESSAGE).center(CALENDAR_WIDTH)
    year = "{year}\n".format(year=current_yr).rjust(8, ' ')
    txt_builder = []
    txt_builder.append(init_msg)
    txt_builder.append("\n\n")
    txt_builder.append(year)

    cal = calendar.Calendar(calendar.MONDAY)
    for m, month_name in MONTHS.items():
        month = cal.itermonthdays(current_yr, m)
        days = "".join(
            [get_weekday_format(current_yr, m, day)
                for day in month if day != 0]
        )

        txt_builder.append("{month_name}{days}\n".format(month_name=month_name,
                                                         days=days))
    return "".join(txt_builder)


def get_weekday_format(year, month, day, include_weekend=True):
    """return numeric day in string if weekday else day with WEEKEND_SYMBOL"""
    weekend = [calendar.SATURDAY, calendar.SUNDAY]
    d = calendar.weekday(year, month, day)
    # highlight_wkend = False
    # global WEEKEND_SYMBOL

    # WEEKEND_SYMBOL = ' '
    if d in weekend:
        if include_weekend:
            return "{ws}{day}  ".format(ws=WEEKEND_SYMBOL, day=day)
        else:
            return ""

    return " {day}  ".format(day=day)


class ChainsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.insert(edit, 0, dbtc())
        self.view.run_command('highlight_today')


class MarkTodayAsDone(sublime_plugin.TextCommand):
    def run(self, edit):
        regions = self.view.get_regions(TODAY_KEY)

        if regions:
            sel = self.view.sel()
            sel.clear()
            sel.add(regions[0])
            self.view.run_command('mark_as_done')


class HighlightTodayCommand(sublime_plugin.TextCommand):
    def run(self, edit):

        today = datetime.date.today()
        month_name = calendar.month_name[today.month]
        # find line that match month and day in same line
        m_regex = (r"^\s+{month}\:.+[\s\.]{day}[{norm_sym}{done_sym}].*$"
                   .format(month=month_name,
                           day=today.day,
                           norm_sym=NORMAL_SYMBOL,
                           done_sym=DONE_SYMBOL))

        found_region = self.view.find(m_regex, 0)

        if found_region != NOT_FOUND:
            line_r = self.view.line(found_region)
            line = self.view.substr(line_r)
            day_format = get_weekday_format(today.year, today.month, today.day)
            with_symbol = ("{day}{done_sym} "
                           .format(day=day_format.rstrip(' '),
                                   done_sym=DONE_SYMBOL))

            if with_symbol in line:
                day_str = with_symbol
                scope = "today.done.chain"
            else:
                day_str = day_format
                scope = "today.chain"

            start_i = found_region.begin() + line.index(day_str)
            end_i = start_i + len(day_str)
            # highlight region, reversed start/end
            # so that the cursor starts from the beginning
            # regions.add(sublime.Region(end_i, start_i))
            self.view.erase_regions(TODAY_KEY)
            regions = [sublime.Region(end_i, start_i)]
            self.view.add_regions(
                TODAY_KEY,
                regions,
                scope,
                "dot",
                sublime.DRAW_SQUIGGLY_UNDERLINE
            )


class HighlightTodayOnActivated(sublime_plugin.EventListener):
    def on_activated(self, view):
        # only execute when the current view has DBTC syntax
        if view.settings().get('syntax').endswith('Chains.tmLanguage'):
            view.run_command('highlight_today')


def chain_month(view):
    regions = view.sel()

    for r in regions:
        multi_lines_r = view.split_by_newlines(r)

        for subregion in multi_lines_r:
            line_r = view.line(subregion)
            line = view.substr(line_r)

            # using a generator to filter out line that starts with with monthname
            # first hit/find is used
            month_num = next((m for m, name in MONTHS.items() if line.startswith(name)), None)

            # only continue processing for lines
            # that starts with one of the month names
            if month_num:
                in_region = expand_whole_word(view, subregion)
                sentence = view.substr(in_region)
                words = sentence.split()
                print("'"+sentence+"'")

                for w in words:
                    is_weekend = WEEKEND_SYMBOL in w
                    is_done = DONE_SYMBOL in w
                    if is_weekend:
                        w = w.replace(WEEKEND_SYMBOL, '')
                    if is_done:
                        w = w.replace(DONE_SYMBOL, '')

                    if w.isdigit():
                        day_num = int(w)
                        if 1 <= day_num <= 31:
                            day = {"str": w,
                                   "str_norm": w+NORMAL_SYMBOL,
                                   "str_done": w+DONE_SYMBOL,
                                   "is_weekend": is_weekend,
                                   "is_done": is_done,
                                   "date": datetime.date(
                                       datetime.date.today().year,
                                       month_num, day_num
                                   )}

                            yield day, in_region


class MarkAsDoneCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        for day, in_region in chain_month(self.view):
            # make sure you cannot mark done ahead of time
            if not day["is_done"] and not is_future(day["date"]):
                search_replace(self.view, edit,
                               search_s=day["str_norm"],
                               replace_s=day["str_done"],
                               in_region=in_region,
                               date=day["date"])


class UnmarkDoneCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        for day, in_region in chain_month(self.view):
            if day["is_done"]:
                search_replace(self.view, edit,
                               search_s=day["str_done"],
                               replace_s=day["str_norm"],
                               in_region=in_region,
                               date=day["date"])


class DoneToggleCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        for day, in_region in chain_month(self.view):
            # ignore if day is not done and in the future.
            # We do not want to toggle this
            if not day["is_done"] and is_future(day["date"]):
                continue

            search_s = day["str_done"] if day["is_done"] else day["str_norm"]
            replace_s = day["str_norm"] if day["is_done"] else day["str_done"]

            search_replace(self.view, edit,
                           search_s,
                           replace_s,
                           in_region,
                           day["date"])


class ChainsNewDocCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.new_file()
        regions = view.sel()
        view.set_syntax_file('Packages/Chains'
                             '/Chains.tmLanguage')
        view.run_command("dont_break_the_chain")
        # view.run_command("highlight_today")
        msg_r = view.find(INITIAL_MESSAGE, 0, sublime.LITERAL)
        region = region_cursor_start(msg_r)
        regions.clear()
        regions.add(region)


def search_replace(view, edit, search_s, replace_s, in_region, date):
    """search and replace text within a given region"""
    word_r = get_subregion(view, search_s, in_region)

    if word_r != NOT_FOUND:
        view.replace(edit, word_r, replace_s)
        if date == datetime.date.today():
            view.run_command('highlight_today')
    else:
        print("NOT FOUND!")


def get_subregion(view, word, in_region):
    sentence = view.substr(in_region)

    if word in sentence:
        i = sentence.index(word)
        start_r = in_region.begin() + i
        end_r = start_r + len(word)
        return sublime.Region(start_r, end_r)
    else:
        return NOT_FOUND


def expand_whole_word(view, region):
    """increase point/region until reaches \s, \n
       and DONE_SYMBOL, returns word region"""
    # deal with edge cases where the cursor is inbetween two dates
    if region.empty() and view.substr(region.b) == ' ':
        # peek to the right for any characters
        r = sublime.Region(region.a, region.b+2)
        c = view.substr(r).strip()

        if c:
            return expand_end_of_word(view, r)

        # peek to the left for any characters
        r = sublime.Region(region.a-2, region.b)
        c = view.substr(r).strip()

        if c:
            return expand_beginning_of_word(view, r)

    return expand_end_of_word(view, region)


def expand_beginning_of_word(view, region):
    """decrease the beginning region by 1 until /s and WEEKEND_SYMBOL is hit"""
    # print("expand begin:'" + view.substr(region) + "'",
    #    region, "'" + view.substr(region) + "'")
    beginnings = [' ', WEEKEND_SYMBOL]

    while not any(view.substr(region).startswith(c) for c in beginnings):
        region = add_region_by(region, -1, at_the="beginning")
    # make sure that we end region with NORMAL_SYMBOL,
    # as the space might be replaced with DONE_SYMBOL
    if not view.substr(region).endswith(NORMAL_SYMBOL):
        region = expand_end_of_word(view, region)
    return region


def expand_end_of_word(view, region):
    """increase the end region by 1
       until NORMAL_SYMBOL/WEEKEND_SYMBOL /n is hit"""
    word_r = view.word(region)
    endings = [NORMAL_SYMBOL, DONE_SYMBOL, '\n']

    while not any(view.substr(word_r).endswith(char) for char in endings):
        word_r = add_region_by(word_r, 1, at_the="end")
    return word_r


def add_region_by(region, by_num, at_the):
    """add the given number(positive/neg) to region at the given end"""
    if region.empty():
        return region

    bothends = {"beginning": region.begin(), "end": region.end()}
    end_value = bothends.get(at_the, region.end())

    if region.a == end_value:
        region.a += by_num
    if region.b == end_value:
        region.b += by_num
    return region


def region_cursor_start(region):
    """swap region range so that the end region would be at the beginning
    so cursor starts from the beginning when highlighted"""
    if region.b > region.a:
        region.a, region.b = region.b, region.a
    return region


def is_future(unknown_date):
    return (unknown_date > datetime.date.today())
