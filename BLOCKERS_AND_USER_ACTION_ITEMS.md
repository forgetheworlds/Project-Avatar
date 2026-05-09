# Blockers & User Action Items

**Last updated: May 9, 2026**

## Hardware (User Purchase Required)

| Item | Recommendation | Est. Cost | Status |
|------|---------------|-----------|--------|
| FC+ESC | MicoAir H743 AIO 35A | $59 | ⬜ Not ordered |
| Frame | SpeedyBee Master3X (3-3.6") | $30 | ⬜ Not ordered |
| Motors | 1505 3800KV ×4 | $36 | ⬜ Not ordered |
| Props | Gemfan 3.5" tri-blade ×8 | $8 | ⬜ Not ordered |
| GPS | GOKU GM10 Nano V3 | $25 | ⬜ Not ordered |
| ESP32 | XIAO ESP32-S3 ×2 | $15 | ⬜ Not ordered |
| RX | ELRS Nano RX | $15 | ⬜ Not ordered |
| Battery | 4S 850mAh LiPo ×2 | $30 | ⬜ Not ordered |
| Camera | Hawkeye Thumb 4K | $60 | ⬜ Not ordered |
| Pump | Micro diaphragm 12V | $8 | ⬜ Not ordered |
| Servo | MG90S metal gear ×2 | $10 | ⬜ Not ordered |
| Reservoir | 15ml syringe or IV bag | $2 | ⬜ Not ordered |
| Nozzle | 3D printed or brass | $3 | ⬜ Not ordered |
| MOSFET | IRFZ44N for pump | $1 | ⬜ Not ordered |
| Wiring | Silicone, JST connectors | $10 | ⬜ Not ordered |
| **Total** | | **~$312** | |

## Accounts / Credentials Needed

| Item | Needed For | Status |
|------|-----------|--------|
| TinyFish API key | Research | ✅ Configured |
| GitHub | Code hosting | ✅ Available |
| npm/pip | Package installs | ✅ Available |
| Himaya email | Dad job pipeline | ✅ Configured |

## Regulatory / Legal

| Item | Status |
|------|--------|
| Sub-250g drone — no registration needed in Canada | ✅ Clear |
| Senior Assassins game rules — check school policy | ⚠️ Needs verification |
| Flying near people — safety considerations | ⚠️ Document before flight |

## Unresolved Uncertainties

| Item | Notes |
|------|-------|
| MicoAir vs SpeedyBee FC availability | Both available, compare lead times |
| Hawkeye Thumb 4K gyro sync reliability | Mixed reports — test before committing |
| Water pump spray range at 12V | Test ground-level before mounting |
| CV latency over WiFi | Profile in simulation |
| Protection mode legality at school | Check with game organizers |

## Remaining User-Dependent Tasks

1. **Purchase hardware** when ready
2. **Physical assembly** of drone frame and electronics
3. **Real-world flight testing** — tethered first, then free flight
4. **School/game permission** for water gun drone operation
5. **Final payload integration testing** — water gun aim accuracy

## What's Being Built Without User

- ✅ Full ArduPilot SITL simulation environment
- ✅ MCP tool server for LLM control
- ✅ Mobile PWA control interface
- ✅ CV pipeline (YOLOv8 + tracking)
- ✅ Telemetry dashboard
- ✅ Modular payload interface specs
- ✅ Architecture documentation
- ✅ Testing infrastructure
- ✅ CI/CD deployment automation
