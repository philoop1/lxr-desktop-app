# Firmware image archive

These are exact update images (`LXRV2IMG` format), kept separately from the
working `build/` directory. They are **not** full-flash or bootloader images.

| Image | Source | Size | SHA-256 |
| --- | --- | ---: | --- |
| `LXR_V2_V1.7_baseline.img` | Unchanged desktop 1.7 source; GCC 14.3 baseline | 274,704 bytes | `B34C0C3A946D02C5CEE624351A44C2597694B4832FDAA9CBAEB3627F84979AFE` |
| `LXR_V2_V1.7_Mutador0.1.img` | `feature/pch-cpu` at `af7feb3`; Pch and CPU meter | 275,132 bytes | `C5D2AE5C0F07C0A06AC888457AA051448B2380111373A7CA7E09D126853B983F` |
| `LXR_V2_V1.7_Mutador0.1.1.img` | `fix/perf-pattern-morph`; PERF pattern shortcut and morph update fix | 275,220 bytes | `047992BA5A9EEDEA29A05A33DA6E0D79C6C1D7268EE8A33A2CA59AE2DD18B9B8` |
| `LXR_V2_V1.7_Mutador0.1.2.img` | `feature/global-load-switches`; shuffle and Morph load policy | 275,588 bytes | `75CC47E9B862CB58F3F3492190BEA6356276D050F07D395BA5F5B64A41C50148` |
| `LXR_V2_V1.7_Mutador0.1.3.img` | Master sample rate across Morph range; based on `9c98ebe` | 275,636 bytes | `9A886E68023BCFA486CFD78D7887398D4AA7B0F8F840A09E6FBD76D400F47508` |
| `LXR_V2_V1.7_Mutador0.1.4.img` | Adds global lsr switch; includes 0.1.3 master srt behavior | 275,772 bytes | `6864825660889E887FA162E2439DAE4294168429205BD69ED1AE6716825CD654` |
| `LXR_V2_V1.7_Mutador0.1.6.img` | Mutador note routing, Pch transpose, CC channel-index fix | 276,884 bytes | `3B6F171539FAD1A9E84ED1B0835E5C2D193FEC67C40EEEA287FC35A4D905D58D` |
| `LXR_V2_V1.7_Mutador0.1.7.img` | Full Mutador pitch, global/Voice bend, PERF gpt/pbr | 278,508 bytes | `76298CE0FAA7D6F01C48754E91A702A8B1A6D86A493EF852BA12D3D7D7B9E834` |
| `LXR_V2_V1.7_Mutador0.1.8.img` | GDC, 606 link, RST/CSR, BC Scarcity and PST | 283,600 bytes | `F07720D86A87A9F0E849494A2FBFCD53EBA0F17911E0AB755B86DD8104108C01` |
| `LXR_V2_V1.7_Mutador0.1.9.img` | Intermediate Accent/Delay build before exact triplet-rate correction | 291,748 bytes | `410ACCC64D637874915FD7DA6962BCE7A1C12DD2C38A3EA3C0C09EFBAD1876B5` |
| `LXR_V2_V1.7_Mutador0.1.10.img` | Accent, MIDI Delay, CNT and exact triplet rates; device test pending | 291,748 bytes | `3F0E6BA8BEEA1D5887615818959D004C2DFE60115D3D32810C5B5943AF7AB824` |
| `LXR_V2_V1.7_Mutador0.1.12.img` | Four-point Groove, 192 PPQ notes/Delay, SHIFT+4, lsh hold and project-load fixes; device test pending | 294,876 bytes | `14868D0050D68DD322AB7B550B298427758B3A0EDAC06AAC792395A1CDE8F621` |
| `LXR_V2_V1.7_Mutador0.1.13.img` | lki/aut labels, CPU slot swap and explicit 16sh clock; new controls pending device test | 295,076 bytes | `DCBF5B7176BA30D80DE17DA99E08C7E4C1FCA85C5CEDFC63E4B7F8FC5154BB07` |
| `LXR_V2_V1.7_Mutador0.1.14.img` | Step selection, scale grid, hi-hat, sends, VCAs, master filter and startup label; device test pending | 304,100 bytes | `F2FA7E606D816036E2FCD58B12950177313E5539F0429F5C7985CA461949E3CD` |
| `LXR_V2_V1.7_Mutador0.1.15.img` | Snare Noise Envelope, drum Ring mode and MIDI Clock Offset; device test pending | 306,232 bytes | `36197B8199EFBA75828AB720ACDE5DF636F0B12823D0302A3F3CCC417A2F0650` |
| `LXR_V2_V1.7_Mutador0.1.16.img` | Snare Layer, extended COPY, manual MIDI Clock bar start; device test pending | 310,420 bytes | `FCC35C9BC4DC5D0584167E292ACC19F84A5CEB2C10ADC39B65BF25B253619DF1` |
| `LXR_V2_V1.7_Mutador0.1.17.img` | MIDI transport front-panel PLAY state feedback; device test pending | 310,460 bytes | `013EE2DC1404661A4EF51D316F22C639D75A7B12AA1E69BB027C70F23EF0294C` |
| `LXR_V2_V1.7_Mutador0.1.18.img` | Dedicated SHIFT pages; hidden VCA view; initial Snare layout | 311,252 bytes | `F0C1D78B7218463D15163BEFFAF92D16FE392200AAB1E5B7D8B37F438CFE5B61` |
| `LXR_V2_V1.7_Mutador0.1.19.img` | Corrected Snare names/OSC/FM ordering and parameter-page switching | 311,204 bytes | `669093149F2BFE62DFB0D55F04376F50B4F0F826C0A1B5574C5F856A9D574558` |
| `LXR_V2_V1.7_Mutador0.1.20.img` | Seven Snare LFO/velocity/automation destinations | 311,748 bytes | `9E84DC6E96A6BB6D6A0B5071D6F8D3424FB82A61E572F798EB56300DFAE63CA8` |
| `LXR_V2_V1.7_Mutador0.1.21.img` | Snare voice CC 112-118 | 312,164 bytes | `CE19BDA47F471949EBBDAA117AE49A3FCEC0C24D3E112716FA003FC151503D09` |
| `LXR_V2_V1.7_Mutador0.1.22.img` | Stray/Glide, full Voice CC map and confirmed per-pattern Scale; card hash verified | 317,324 bytes | `088D3C994528BB06B71549802068C5A0FFB77E49E72774517F92974B4180705F` |
| `LXR_V2_V1.7_Mutador0.1.23.img` | Any-mode SHIFT+1, Mutador rvl and overall avl after rvl; hardware test pending | 318,284 bytes | `585F0CEDEC5C628A733E3434BA6EFA781EAE144BE80B14842913877D3F8CF616` |
| `LXR_V2_V1.7_Mutador0.1.24.img` | Default Step velocity 100; one-time card velocity conversion | 318,284 bytes | `ACE03935A58965A030232769B8E3713BC4B4874B0A8755D9A74A000082FF8DD7` |
| `LXR_V2_V1.7_Mutador0.1.25.img` | Proportional AVL gain after RVL; card hash verified | 318,260 bytes | `6DFB73370CAD9E8EC5E87C05F6E8B74EA29CD7D800917F1851C3B4A214D0F492` |
| `LXR_V2_V1.7_Mutador0.1.26.img` | CC bounds, MIDI reentry protection, project loading name; device retest pending | 318,260 bytes | `462432BA7278419494974FA9181EBB23D009E3837726A298711A31E924443E8E` |

| `LXR_V2_V1.7_Mutador0.1.27.img` | Kit-loader bounds guard; hardware freeze persisted | 318,084 bytes | `10A5980FD81A1B2C2A4B9C2C88C5BD63EF738DD16BBBA38FB65B9A44F0929EF1` |
| `LXR_V2_V1.7_Mutador0.1.28.img` | Immediate kit selector fix; targeted hardware retest passed | 318,108 bytes | `08FD79C072EE4B068913E5563CD70565689DC028C3596879E278564715325C03` |
| `LXR_V2_V1.7_Mutador0.2.img` | Random per played Step LFO, Flam Probability, compatible pattern/kit extensions; card verified | 323,084 bytes | `F58CF6793F27726F51FD504494E62571B41694213F0D7F837745DEE4A8A4D0AF` |

To install one version, copy **only that one `.img`** to the root of an SD
card and remove older `LXR*.img` update files from the card first. Keep this
archive off the card. Mutador 0.1 booted on physical hardware and showed a
67% CPU reading, but morph had no audible effect in the reported test.
The user confirmed Morph target selection works in 0.1.2. Its master sample
rate did not control the Morph target; 0.1.3 addresses that behavior and still
needs separate hardware testing as a standalone image. The user reported
that 0.1.4 (which includes that change and lsr) works on the instrument.
Persistence and full regression checks remain open. The baseline image passed a
limited emulator smoke test.

The Git repository preserves these image bytes and their source history. A
second copy on another drive or cloud service is still needed for protection
against failure of this drive.

0.1.6 includes all 0.1.4 changes and has passed release build and native
MIDI contract tests. Its physical-device tests are pending. No separate
0.1.5 image was produced.

0.1.7 passed release build and native pitch parity tests, and its copy on F:
was hash verified. Physical-device validation remains open.

0.1.8 passed release and native performance/MIDI tests and was hash-verified
on F:. 0.1.7 was locally backed up before removing its root update image.
Physical-device checks remain pending.

0.1.12 passed the release build and native Groove/reference/integration tests.
Its copy on F: was hash-verified; the prior 0.1.10 root update was locally
backed up before removal. Physical-device tests remain open.

The user subsequently reported that 0.1.12 works. 0.1.13 passed release and
clock-output tests and was hash-verified on F:. Its new controls need a
device check; the prior card image is preserved in the local backup.

0.1.22: Stray/Glide, common Voice CC map (excluding Membrane), and per-pattern
Scale 2/4/6/8/12/16/24/32 with long PERFORMANCE and encoder confirmation.
ARM build and native checks passed; physical-device testing remains open.
File: LXR_V2_V1.7_Mutador0.1.22.img (317324 bytes).
SHA-256: 088D3C994528BB06B71549802068C5A0FFB77E49E72774517F92974B4180705F.
This image was copied to SD card F: on 2026-10-31 and its SHA-256 verified.
The former 0.1.19 image is retained here and in the dated card-image backup.

0.1.23 passed the ARM release build and native velocity/shortcut, MIDI,
performance and storage checks. It adds any-mode SHIFT+Step 1 and rvl/avl.
This image is archived locally and was copied to F: on 2026-10-31 with
SHA-256 verification. The former 0.1.22 image is preserved in the archive
and the dated card-image backup.

0.1.25 passed the ARM release build and 196491 native velocity/shortcut
assertions. AVL +50 means x1.5 and +100 means x2, clipped at 127; quieter
Steps retain their relative dynamics until clipping. New/reset Steps default
to velocity 100. The one-time active PROJ/TMP conversion was backed up and
verified separately; it is not performed automatically by the firmware.
0.1.25 was copied to F: on 2026-10-31 and its SHA-256 verified. Physical-device
testing remains open. The former 0.1.24 card image is backed up locally.

Mutador 0.2.1: `LXR_V2_V1.7_Mutador0.2.1.img`, 323092 bytes, SHA256 `43016B34C3BDAB6316535F059889B628CA4A31FA2B0C2D820E895CFED05AB9AF`. Built and tested on host; device retest pending. Copied to SD F: and SHA256 verified; old update image backed up before removal.

Mutador 0.2.2: LXR_V2_V1.7_Mutador0.2.2.img, 323284 bytes, SHA256 095A1A96B6BCF0A8DF5E01317DD4E033DE46789C0CA174571D3B86E020530978.

Mutador 0.2.3: `LXR_V2_V1.7_Mutador0.2.3.img`, 323348 bytes, SHA256 `021569213D849D80AFE1A4A21BD621F5C4C600192C1417D27516CA232B50AD79`. Hardware retest pending.

Mutador 0.2.4: `LXR_V2_V1.7_Mutador0.2.4.img`, 323420 bytes, SHA256 `71641EF6B46EE127889E207C669D447BBBE355B0E271B7BF50E08A1581C7F2F8`. Hardware retest pending.

Mutador 0.2.5: `LXR_V2_V1.7_Mutador0.2.5.img`, 323460 bytes, SHA256 `2E21DEC9570ED5A2BA10B0D916FC14EFBD97B2DCB499E09C4034C582E863DFA5`. Hardware dst-change retest pending.

Mutador 0.2.11: `LXR_V2_V1.7_Mutador0.2.11.img`, 331300 bytes, SHA256 `0421C3E632DF2806ADA1C3D4BF4C62F25B7EAC3D718BEE69A287ED64306B6A6D`. Copied to SD F: and hash verified; physical SCT navigation test pending.

Mutador 0.2.12: `LXR_V2_V1.7_Mutador0.2.12.img`, 334820 bytes, SHA256 `61CBBCA7D922443F38DECEDBF58CD239FACA3C77F14FD75EFDCE84A548AB5341`. Cross-project transfer and overwrite confirmation need hardware validation.
SD F: 0.2.12 copied and hash verified; old image archived.

Mutador 0.2.13: `LXR_V2_V1.7_Mutador0.2.13.img`, 336996 bytes, SHA256 `5E50B7C2AA635E899DE37CF28EF7A79FFE5CC56371AFBC900889FA485D30EE9A`. Copied to SD F: and hash verified; old image backed up. Project transfer, P+K and the active-slot import need hardware validation.

Mutador 0.2.14: `LXR_V2_V1.7_Mutador0.2.14.img`, 336996 bytes, SHA256 `905761062A2FAA68C36C11617084D8D57EB84589533798FD4C09658B393373A3`. Fixes the PROJECT double-press window. Copied to SD F: and hash verified; device retest pending.

Mutador 0.2.15: `LXR_V2_V1.7_Mutador0.2.15.img`, 338300 bytes, SHA256 `FB924EE519640BA145CD7C8DDF465ACF2041C3D361E2339EEF1C54A326E1CAC4`. Adds LXR1 performance import. Copied to SD F: and hash verified; device test pending.

Mutador 0.2.16: `LXR_V2_V1.7_Mutador0.2.16.img`, 339164 bytes, SHA256 `CB9EFED3A4C72944FF2F11E2CE0CC7B3C25F78A6BEFAA9F26A27C26EFB9528C1`. Transfer imports now reach the running project. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.17: `LXR_V2_V1.7_Mutador0.2.17.img`, 339348 bytes, SHA256 `4B9C9FA1EA5F55B517E2EA223F74F1EE1945BCFF0B1352CCA4B50BE0748AEEC1`. Encoder bank selection and long LOAD shortcut. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.18: `LXR_V2_V1.7_Mutador0.2.18.img`, 338028 bytes, SHA256 `703EC9754E072CC558E8125AFB11DBB9F01997168F3DE1BF0A56ABDD147B1CE6`. Live sct with real step time and CC 88-91. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.19: `LXR_V2_V1.7_Mutador0.2.19.img`, 338092 bytes, SHA256 `80A18D336FD1B53F623A31FCDF37BB16BF18DC391303D2C7388E74077EB99F5B`. Pattern rate survives leaving a pattern; beat LED on ternary rates. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.20: `LXR_V2_V1.7_Mutador0.2.20.img`, 338308 bytes, SHA256 `2C17F4482B3228387CA468F5C510F88531C685AC031BF81529B72370C70F094B`. spd replaces scl. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.21: `LXR_V2_V1.7_Mutador0.2.21.img`, 338812 bytes, SHA256 `9FE652FDDC384965DE6D534EF091A4823D5DFB32C18E814A5F348265B28BD9C1`. Rate 24/32 sets default track length; PLAY starts at once on clock without MIDI START. Not yet on SD; hardware test pending.

Mutador 0.2.22: `LXR_V2_V1.7_Mutador0.2.22.img`, 339628 bytes, SHA256 `B958AE11784F9628F7AA9FC40067D2F90AA1363B89D038A104A5CD92176D42F3`. New Pch CCs for controls that were menu-only. Not yet on SD; F: holds 0.2.20. Hardware test pending.

Mutador 0.2.23: `LXR_V2_V1.7_Mutador0.2.23.img`, 339748 bytes, SHA256 `F83C5EC848C37C2A9514418D4B8D292A544A3BB2C25256E45BBEF4D23E33C71D`. The 0.2.22 Pch CCs need a Pch of their own. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.24: `LXR_V2_V1.7_Mutador0.2.24.img`, 339708 bytes, SHA256 `FE0D3C60554B80188A5303FDB4EE7927154EC7D62B126EA9892C4608CFA9C019`. FX sends on SHIFT + Step 5; correct startup version. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.25: `LXR_V2_V1.7_Mutador0.2.25.img`, 341100 bytes, SHA256 `3B11345DFC9072D017B80EF4656BB1021C68F6B930CF3C67ED547EB51E1F5543`. Drum modes `exp` and `pd`. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.26: `LXR_V2_V1.7_Mutador0.2.26.img`, 341236 bytes, SHA256 `04C403114F49E8D2367C226FDEB10BD08574825D1641AF29523B00B3A70EBBB2`. Pch CC70-75. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.27: `LXR_V2_V1.7_Mutador0.2.27.img`, 345764 bytes, SHA256 `51C9AD20A5CA6ED2ECF83EB6D1166BD1B608FAFE42E5100A685A9CA12ED1B0AB`. Reverb, FX Dry/Wet destination, `shu` moved. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.28: `LXR_V2_V1.7_Mutador0.2.28.img`, 345764 bytes, SHA256 `57B16CCFAC941BACDC173BCCA93BAB53F4DB13F08005A43B917FB243E4764CFC`. Menu navigation fix. Copied to SD F: and hash verified; hardware test pending.

Mutador 0.2.29: `LXR_V2_V1.7_Mutador0.2.29.img`, 345636 bytes, SHA256 `D13245BBFBFF057062EC933046A5851BDCB9D1614160C20333E9DE7EA03B90A0`. Half-rate reverb for CPU; hardware test pending.
Copied to SD F: and hash verified.

Mutador 0.2.30: `LXR_V2_V1.7_Mutador0.2.30.img`, 341164 bytes, SHA256 `736BABA5F0C40C8B48797581F71BAE4D73126BFAD6994DAD76CE27FE38086AB9`. Reverb removed; hardware test pending.
Copied to SD F: and hash verified.

Mutador 0.2.31: `LXR_V2_V1.7_Mutador0.2.31.img`, 343180 bytes, SHA256 `95B63E2F6C5CA54905A6514CE80349A0E573C7B7708050092BD70C43C93B1590`. Tape delay FX; hardware test pending.
Copied to SD F: and hash verified.

Mutador 0.2.32: `LXR_V2_V1.7_Mutador0.2.32.img`, 343204 bytes, SHA256 `808B3D297FB79B8CD3D264DB11C270B63D4744735E0D19C2571C8A682AD43630`. Knob 1 on Load/Save; hardware test pending.
Copied to SD F: and hash verified.

Mutador 0.2.33: `LXR_V2_V1.7_Mutador0.2.33.img`, 343580 bytes, SHA256 `5D9D977536A050D68DE11D7992463D77E9A6493E42998DF5193FF0D9FBB581E8`. Tape delay ignores MIDI clock jitter; hardware test pending.

Mutador 0.2.34: `LXR_V2_V1.7_Mutador0.2.34.img`, 343772 bytes, SHA256 `F073FA445154A41C2B509F895D37E02B868F94ECD3E6F56A8F7B88137128DB3E`. Tape feedback over 100 %, fine +-20 %; hardware test pending.

Mutador 0.2.35: `LXR_V2_V1.7_Mutador0.2.35.img`, 343988 bytes, SHA256 `A4E3508CC4FCD7D21323E0BA24A4E46868F9ABC24D183B641013E68A98509478`. CC morph glides; hardware test pending.

Mutador 0.2.36: `LXR_V2_V1.7_Mutador0.2.36.img`, 346940 bytes, SHA256 `932F2540FCAB34876B41845177B9034857DCC200A9B572A79E4B062FD14C6068`. User wavetables for Drum 1-3; hardware test pending.

Mutador 0.2.37: `LXR_V2_V1.7_Mutador0.2.37.img`, 348212 bytes, SHA256 `2C0ED1555EE785024EE9EB4BB43A2CF8FC30E7AE058EC13A18193645BF78238F`. Wavetable plain-mode fix, PWM scan; hardware test pending.

Mutador 0.2.38: `LXR_V2_V1.7_Mutador0.2.38.img`, 348588 bytes, SHA256 `CF13C06AFEDA2BC986384C9D3915405775BB8D0E151CB0CC08C5FC7F5FE920D0`. Serum wavetables, PWM scans the frames; hardware test pending.

Mutador 0.2.39: `LXR_V2_V1.7_Mutador0.2.39.img`, 348780 bytes, SHA256 `0B6EBD9247AF8CC9C05953FCDA5DC5D71A11ED81FDA7129086467347FA8A005A`. Flash size test display; hardware test pending.

Mutador 0.2.40: `LXR_V2_V1.7_Mutador0.2.40.img`, 348884 bytes, SHA256 `5CE27F149D4DD0374BE52755C43D41738A4CEF0106CAFB1AB57B935356DB2CC5`. Wavetables in sectors 7 to 11, 284 frames; hardware test pending.

Mutador 0.2.41: `LXR_V2_V1.7_Mutador0.2.41.img`, 348148 bytes, SHA256 `81E4D46B6B497551BB1C3377CDAE0546FFA5C3AB51D1B5E37286CADEE9F1361F`. 32 wavetable slots; hardware test pending.

Mutador 0.2.42: `LXR_V2_V1.7_Mutador0.2.42.img`, 349748 bytes, SHA256 `5BB3EC4E43893DEB3D93CE20682FCC8A9B675B74868A93227225F549BF4C6F64`. Slot scan, level blend, gliding scan; hardware test pending.

Mutador 0.2.43: `LXR_V2_V1.7_Mutador0.2.43.img`, 349748 bytes, SHA256 `5B891E0670D66A6ED606EAE4F7B38E52168F57893FB58B1938BE77EB389867CD`. Dither click fix; hardware test pending.

Mutador 0.2.44: `LXR_V2_V1.7_Mutador0.2.44.img`, 349748 bytes, SHA256 `A449FC4EEBAC5DA9E3529E6D118DBBF54FF22BA8AE83D655B620F8E3CC1C0826`. Envelope end click fix; hardware test pending.

Mutador 0.2.45: `LXR_V2_V1.7_Mutador0.2.45.img`, 349748 bytes, SHA256 `D39C5B0003F8A4467A55D8E0600A1F1C89EC435FBC3AD65F03D96D12BA2DE6F4`. Wavetables as drum modulator; hardware test pending.

Mutador 0.2.46: `LXR_V2_V1.7_Mutador0.2.46.img`, 349868 bytes, SHA256 `7DBF15829541485DC1AAAE65A02808E46D8D04D9D8B581936A7455690746B023`. PD click fix, pitch slope 127 fix; hardware test pending.

Mutador 0.2.47: `LXR_V2_V1.7_Mutador0.2.47.img`, 350124 bytes, SHA256 `A25C86C9782C397D265BD2BF719432D9DF389B96C989A25D6CB51A3AE792E2FE`. Project transfer "Copy failed" fix (_FS_LOCK 2); hardware test pending.

Mutador 0.2.48: `LXR_V2_V1.7_Mutador0.2.48.img`, 350748 bytes, SHA256 `62EC3D90AD1F6F3B4B37EEA771F8FFD19FA08D664A7ECCEEA7E8B0B81A582F6D`. Flam 2+1..8+1, Kit transfer while playing; hardware test pending.

Mutador 0.2.49: `LXR_V2_V1.7_Mutador0.2.49.img`, 351964 bytes, SHA256 `6CDE5D36453ACC5B95DCBE22AD382BB50EFCEDF5453CDCC3A1C69629764061EB`. LFO one-shots/xtr, Snare exp/pd, wavetables on Snare/Cymbal/Hihat; hardware test pending.

Mutador 0.2.50: `LXR_V2_V1.7_Mutador0.2.50.img`, 351980 bytes, SHA256 `DFF9586236A2C5A96EEF96D797F232B273699D222BD661CACED7D5791279828F`. Snare wmd=FM fix; hardware test pending.

Mutador 0.2.51: `LXR_V2_V1.7_Mutador0.2.51.img`, 354796 bytes, SHA256 `992369571D83E643426E6E318986F137478994A374245B7094CBC667AD0508E9`. User samples (SAMPLES/SAMPLES.BIN); hardware test pending.

Mutador 0.2.52: `LXR_V2_V1.7_Mutador0.2.52.img`, 355808 bytes, SHA256 `B40CF56E00D52CE084BBAE555FDDD09646BD7FC06BE01F363F09F02C8A95610B`. Long-press swap, used-pattern view; hardware test pending.

Mutador 0.2.53: `LXR_V2_V1.7_Mutador0.2.53.img`, 355944 bytes, SHA256 `8ACF3439D8CDF37F74204491768FC13323FC7F3F3C5BFFDEB7724AD63C8A6946`. Step edit long press; hardware test pending.

Mutador 0.2.54: `LXR_V2_V1.7_Mutador0.2.54.img`, 357144 bytes, SHA256 `0D1CDA8FB8FAC99D6FFE87AA151E39F630B48DE736841CB5A9B4CBF49B5026D0`. fil moved, avl/sct spacing; hardware test pending.

Mutador 0.2.55: `LXR_V2_V1.7_Mutador0.2.55.img`, 357656 bytes, SHA256 `CBCE7F886B80F6F98408BF369315305696159E40B87FBA0EB0804AB4CF179B32`. Humanize hm1..hm4; hardware test pending.

Mutador 0.2.56: `LXR_V2_V1.7_Mutador0.2.56.img`, 359304 bytes, SHA256 `931C2A1D04EA4BFEEB99C5C8932062106796CCE371E5EB550DB4FDC0F13F7A30`. Flam velocity fvl; hardware test pending.

Mutador 0.2.57: `LXR_V2_V1.7_Mutador0.2.57.img`, 360504 bytes, SHA256 `5419EB5BF3DE16AB8F5E1649ABFD41AFBCB922847DFD3A28244907E5829123AE`. Measurement build for save timing, USB MIDI during saves; hardware test pending.

Mutador 0.2.58: `LXR_V2_V1.7_Mutador0.2.58.img`, 360664 bytes, SHA256 `2F68CC239569EF8C511EDE1D1E4E9DDF8A3ACEAF024EE521E0A6E7206B353545`. MorphKit save to SD, save timing display; hardware test pending.

Mutador 0.2.59: `LXR_V2_V1.7_Mutador0.2.59.img`, 360800 bytes, SHA256 `A68D62FCAA79F12B2372352E8DBA8B446A08CE8CDE481E35A917636644073728`. Save glitch and autosave fixes, MorphKit routing; hardware test pending.

Mutador 0.2.60: `LXR_V2_V1.7_Mutador0.2.60.img`, 360928 bytes, SHA256 `008D3471B6636E2775E046213F2FFBDC4046B036BAE55788D75BA3A4C142D1EA`. Project save glitch fix, kit load measurement; hardware test pending.

Mutador 0.2.61: `LXR_V2_V1.7_Mutador0.2.61.img`, 364128 bytes, SHA256 `B930C1FF309255CCDCBE667DE7C9C637DC63663F1DF5864CC59397276103D78C`. Flam presets (repeats, resolution, velocity, pitch, +1, accelerate/brake) per project; hardware test pending.

Mutador 0.2.62: `LXR_V2_V1.7_Mutador0.2.62.img`, 364360 bytes, SHA256 `B981B0339ED541A55D827BA09FCD17117A50F9DAC99C1DD5C6E042D54E351B0A`. Import page click fix (SD access inside the sample interrupt window); hardware test pending.
