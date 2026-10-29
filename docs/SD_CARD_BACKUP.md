# SD-card data backup

`SD-Card/` is a local backup of an older LXR V2 card, described by its owner
as the version 1.6 state. It contains projects, kits, patterns, songs,
configuration files and samples. The firmware update image was removed from
this backup before import.

`SD-Card/bootloader.img` still exists locally, but `.gitignore` excludes it
from this repository. It is not needed for ordinary firmware updates. In this
source tree `UPDATE_BOOTLOADER` is `0`, so the bootloader-update code is not
built. Keep the local file out of any card copy used for routine updates.

The tracked backup is data for review and recovery. It is not a verified
ready-to-flash card image; test a copy on hardware before relying on it.
