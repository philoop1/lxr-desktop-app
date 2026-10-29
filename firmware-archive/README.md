# Firmware image archive

These are exact update images (`LXRV2IMG` format), kept separately from the
working `build/` directory. They are **not** full-flash or bootloader images.

| Image | Source | Size | SHA-256 |
| --- | --- | ---: | --- |
| `LXR_V2_V1.7_baseline.img` | Unchanged desktop 1.7 source; GCC 14.3 baseline | 274,704 bytes | `B34C0C3A946D02C5CEE624351A44C2597694B4832FDAA9CBAEB3627F84979AFE` |
| `LXR_V2_V1.7_Mutador0.1.img` | `feature/pch-cpu` at `af7feb3`; Pch and CPU meter | 275,132 bytes | `C5D2AE5C0F07C0A06AC888457AA051448B2380111373A7CA7E09D126853B983F` |
| `LXR_V2_V1.7_Mutador0.1.1.img` | `fix/perf-pattern-morph`; PERF pattern shortcut and morph update fix | 275,220 bytes | `047992BA5A9EEDEA29A05A33DA6E0D79C6C1D7268EE8A33A2CA59AE2DD18B9B8` |
| `LXR_V2_V1.7_Mutador0.1.2.img` | `feature/global-load-switches`; shuffle and Morph load policy | 275,588 bytes | `75CC47E9B862CB58F3F3492190BEA6356276D050F07D395BA5F5B64A41C50148` |

To install one version, copy **only that one `.img`** to the root of an SD
card and remove older `LXR*.img` update files from the card first. Keep this
archive off the card. Mutador 0.1 booted on physical hardware and showed a
67% CPU reading, but morph had no audible effect in the reported test.
Mutador 0.1.1 and 0.1.2 still need on-device checks. The baseline image passed a
limited emulator smoke test.

The Git repository preserves these image bytes and their source history. A
second copy on another drive or cloud service is still needed for protection
against failure of this drive.
