"""How the service names what happened, so the browser can say it.

One function, and it is the whole of the contract between the two halves of
this tool: the service answers with a name and the values that fill it, and the
catalogue in `web/lang/` turns that into a sentence in whichever language is
being read.

It lives on its own because everything that can report an outcome needs it, and
the alternative was reaching into `kiosk.py` for it. That module is the whole of
what this tool does to the machine, and a module that only stores a file has no
business importing it to name a refusal.
"""


def told(reason, **values):
    """One answer from this service, as a name and what fills it.

    @param reason - What happened, in a form that does not change with the
      language it is read in. Named `reason` rather than `name`, because that is
      what it is called in the answer and because a value called `name` is one
      of the commonest things an answer carries.
    @param values - Whatever the sentence needs: a count, a machine's name, a
      number of seconds.
    @returns dict with `reason` and the rest beside it.

    A sentence written here could only ever be in one language, and this
    service has no idea which language the person reading it wants. So it says
    what happened and the browser says it in words.

    `tests/test_strings.py` reads every name out of the modules that call this
    and fails where a catalogue cannot say one of them, which is what keeps a
    new answer from reaching the screen as its own name.
    """
    return {"reason": reason, **values}
