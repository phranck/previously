# A test loop that needs nobody at the desk

Everything on the emulator's side is tested in BMNeXT's PC simulator (`tools/hostsim`) on a Mac, built with AddressSanitizer and UndefinedBehaviorSanitizer. On the test Pis, a test build takes a new kernel over the network, restarts, sends its log, and offers a screenshot and keyboard and mouse input, so a change can be verified without somebody sitting at the Pi. The screenshot and input endpoints exist only in test builds, never on a device somebody bought, because they let anyone on the network operate NeXTSTEP.
