# Firmware image archive

These are exact update images (`LXRV2IMG` format), kept separately from the
working `build/` directory. They are **not** full-flash or bootloader images.

| Image | Source | Size | SHA-256 |
| --- | --- | ---: | --- |
| `LXR_V2_V1.7_baseline.img` | Unchanged desktop 1.7 source; GCC 14.3 baseline | 274,704 bytes | `B34C0C3A946D02C5CEE624351A44C2597694B4832FDAA9CBAEB3627F84979AFE` |
| `LXR_V2_V1.7_Mutador0.1.img` | `feature/pch-cpu` at `af7feb3`; Pch and CPU meter | 275,132 bytes | `C5D2AE5C0F07C0A06AC888457AA051448B2380111373A7CA7E09D126853B983F` |

To install one version, copy **only that one `.img`** to the root of an SD
card and remove older `LXR*.img` update files from the card first. Keep this
archive off the card. Neither image has been tested on physical hardware in
this fork; the baseline image passed a limited emulator smoke test.

The Git repository preserves these image bytes and their source history. A
second copy on another drive or cloud service is still needed for protection
against failure of this drive.
