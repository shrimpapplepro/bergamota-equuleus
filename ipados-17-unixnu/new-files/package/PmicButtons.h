// SPDX-License-Identifier: BSD-2-Clause-Patent
// Mi 8 Pro side buttons, read from the PM8998 through EE 0's observer channels of the SPMI arbiter (version 5, SDM845).
// Read only: nothing on the PMIC is written or configured, so a mistake here cannot change a rail, a reset timer or a pin.
//
// From this phone's device tree (logs-mi8pro/live.dts): the arbiter's "core" and "obsrvr" windows, qcom,ee = 0, PON at 0x800 on
// SID 0 with Power (pon-type 0, KEY_POWER) and Volume Down (pon-type 1, KEY_VOLUMEDOWN), and Volume Up on PM8998 GPIO 6, active low.
#ifndef PMIC_BUTTONS_H
#define PMIC_BUTTONS_H
#include <stdbool.h>
#include <stdint.h>

#define PMB_CORE_PA 0x0c440000u
#define PMB_CORE_SIZE 0x1100u
#define PMB_OBS_PA 0x0e600000u
#define PMB_OBS_SIZE 0x100000u

#define PMB_REG_VERSION 0x000u
#define PMB_MIN_VERSION 0x50000000u
#define PMB_REG_APID_MAP(n) (0x900u + 4u * (n))
#define PMB_APID_COUNT ((PMB_CORE_SIZE - 0x900u) / 4u)
#define PMB_MAP_PPID(map) (((map) >> 8) & 0xfffu)
#define PMB_NO_APID 0xffffu

// One channel per APID in the observer window of EE 0.
#define PMB_CHANNEL(apid) (0x80u * (apid))
#define PMB_REG_CMD 0x00u
#define PMB_REG_STATUS 0x08u
#define PMB_REG_RDATA0 0x18u
#define PMB_STATUS_DONE 0x1u
#define PMB_STATUS_ERRORS 0xeu   // failure, denied, dropped
#define PMB_OP_EXT_READL 1u

#define PMB_PON_PPID 0x008u
#define PMB_PON_RT_STS 0x0810u
#define PMB_PON_POWER 0x1u
#define PMB_PON_RESIN 0x2u
#define PMB_GPIO6_PPID 0x0c5u
#define PMB_GPIO6_RT_STS 0xc510u
#define PMB_GPIO6_MODE 0xc540u
#define PMB_GPIO6_EN 0xc546u
#define PMB_GPIO_LEVEL 0x1u

// The bits of NativeHidInput's report 2. Menu (bit 0) is not a key on this phone.
#define PMB_KEY_POWER 0x2u
#define PMB_KEY_VOLUP 0x4u
#define PMB_KEY_VOLDOWN 0x8u

// A one-byte extended read of the peripheral the channel is mapped to; the byte count field stores length - 1.
static inline uint32_t pmb_read_cmd(uint16_t addr) { return (PMB_OP_EXT_READL << 27) | ((uint32_t)(addr & 0xffu) << 4); }

// gpio_trusted stays false until Volume Up has been seen released: a pin nothing configured as an input could read low for ever,
// and that must not look like a key held down.
static inline uint32_t pmb_decode(uint8_t pon, uint8_t gpio, bool gpio_trusted)
{
    uint32_t keys = 0;
    if (pon & PMB_PON_POWER) keys |= PMB_KEY_POWER;
    if (pon & PMB_PON_RESIN) keys |= PMB_KEY_VOLDOWN;
    if (gpio_trusted && !(gpio & PMB_GPIO_LEVEL)) keys |= PMB_KEY_VOLUP;
    return keys;
}

// A new key set counts once two consecutive samples agree (about 10 ms apart in the touch loop).
struct pmb_debounce {
    uint32_t stable;
    uint32_t last;
};

static inline bool pmb_debounce_step(struct pmb_debounce *d, uint32_t sample)
{
    const bool agree = sample == d->last;
    d->last = sample;
    if (!agree || sample == d->stable) return false;
    d->stable = sample;
    return true;
}
#endif
