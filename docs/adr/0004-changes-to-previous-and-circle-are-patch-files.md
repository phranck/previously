# Changes to Previous and Circle are patch files

Previous and Circle stay at a fixed revision of their upstream sources, and every change we make to them is a patch file of its own in the fork, applied by the build in the way `make_all.sh` already applies BMNeXT's patches to Circle (`src/patches/`). That keeps our difference from upstream small and visible, and a new upstream revision is taken by applying the patches to it again. Whether and when a patch is offered to Andreas Grabher, to rsta2 or to jhonnaker1 is decided by phranck case by case.
