"""NeXT's scroller, held to what there actually is to scroll.

A knob says there is more than the view shows. One that stays when there is
nothing more, or does not come when there is, is a scroller telling the reader
something false, and nothing short of a browser laying the page out can see it.
"""

import time

#: What the scroller of Preferences' panel says against what its view holds:
#: how far the content runs past the view, and whether the knob is shown.
PANEL = """
const scroller = document.querySelector("nx-window[name=preferences] nx-scroller:not(.modules)");
const view = scroller.view;
return { over: view.scrollHeight - view.clientHeight,
         shown: !scroller.bars.down.knob.hidden };
"""

#: A Preferences window short enough that the list of six languages runs past
#: its panel while the Monitor module's one group still fits. Measured in
#: Safari Technology Preview: 15 over for the one, and the other fits down to
#: 251, so neither is within a rounding of the line.
SHORT = 260


def choose(desk, module):
    """Picks a module of Preferences, as a click on its cell does."""
    desk.execute_script(
        "document.querySelector(`nx-window[name=preferences] .module[value=${arguments[0]}]`)"
        ".click()", module)
    time.sleep(0.4)
    return desk.execute_script(PANEL)


def test_the_knob_follows_the_module_preferences_shows(desk):
    """Changing module shows one page and hides the other, which changes how
    much there is to scroll without changing the size of anything the
    scroller was watching. The knob has to follow all the same, both ways."""
    desk.execute_script("""
      const window_ = document.querySelector("nx-window[name=preferences]");
      window_.open();
      window_.style.height = arguments[0] + "px";
    """, SHORT)
    time.sleep(0.6)

    languages = choose(desk, "localization")
    assert languages["over"] > 0, "the list should run past a window this short"
    assert languages["shown"]

    monitor = choose(desk, "monitor")
    assert monitor["over"] <= 0, "the Monitor module should fit a window this short"
    assert not monitor["shown"], "the knob stayed after its content went"

    again = choose(desk, "localization")
    assert again["shown"], "the knob did not come back with the content"
