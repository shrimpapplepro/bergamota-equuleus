// SPDX-License-Identifier: BSD-2-Clause-Patent
// Xiaomi Mi 8 Pro (equuleus) touchscreen protocol: ST FingerTip controller, compatible "st,fts", at 0x49 on i2c@a98000.
// Pure event decoding and contact tracking; EnchiladaTouchProbe.cpp owns the bus. Values are the controller's wire protocol as used
// by the phone's own kernel (drivers/input/touchscreen/fts_521), written here independently.
#ifndef FTS_TOUCH_H
#define FTS_TOUCH_H
#include <stdint.h>
#include <stddef.h>

#define FTS_EVENT_BYTES 8u
#define FTS_FIFO_DEPTH 32u
#define FTS_CMD_READ_EVENT 0x86u   // I2C: one 8-byte event per read, id 0 once the FIFO is empty
#define FTS_CMD_SCAN_MODE 0xa0u    // followed by the mode and its settings
#define FTS_SCAN_ACTIVE 0x00u
#define FTS_SCAN_MULTI_TOUCH 0x01u

#define FTS_EVT_NONE 0x00u
#define FTS_EVT_READY 0x03u        // after every reset, including one the controller does by itself
#define FTS_EVT_ENTER 0x13u
#define FTS_EVT_MOTION 0x23u
#define FTS_EVT_LEAVE 0x33u
#define FTS_EVT_ERROR 0xf3u

#define FTS_TYPE_FINGER 1u
#define FTS_TYPE_GLOVE 2u
#define FTS_TYPE_STYLUS 3u

#define FTS_MAX_IDS 16u            // the id is four bits on the wire
// The axes the phone's kernel reports, inclusive: the panel's own pixels.
#define FTS_MAX_X 1079u
#define FTS_MAX_Y 2247u

struct fts_tracker {
    uint16_t x[FTS_MAX_IDS], y[FTS_MAX_IDS];
    uint8_t type[FTS_MAX_IDS];
    uint16_t active;               // bit per id
};

static inline void fts_tracker_clear(struct fts_tracker *t) {
    t->active = 0;
}

static inline unsigned fts_event_id(const uint8_t *e) {return e[1] >> 4;}
static inline unsigned fts_event_type(const uint8_t *e) {return e[1] & 0x0f;}
static inline unsigned fts_event_x(const uint8_t *e) {return ((unsigned)(e[3] & 0x0f) << 8) | e[2];}
static inline unsigned fts_event_y(const uint8_t *e) {return ((unsigned)e[4] << 4) | (e[3] >> 4);}

// Only something touching the glass is a contact: palm, hover and unknown types lift the id instead.
static inline int fts_type_is_contact(unsigned type) {
    return type == FTS_TYPE_FINGER || type == FTS_TYPE_GLOVE || type == FTS_TYPE_STYLUS;
}

// Applies one event; returns 1 when the set of contacts or a position changed.
static inline int fts_event_apply(struct fts_tracker *t, const uint8_t *e) {
    const unsigned id = fts_event_id(e);
    const uint16_t bit = (uint16_t)(1u << id);
    if (e[0] == FTS_EVT_LEAVE) {
        if (!(t->active & bit)) return 0;
        t->active = (uint16_t)(t->active & ~bit);
        return 1;
    }
    if (e[0] != FTS_EVT_ENTER && e[0] != FTS_EVT_MOTION) return 0;
    if (!fts_type_is_contact(fts_event_type(e))) {
        if (!(t->active & bit)) return 0;
        t->active = (uint16_t)(t->active & ~bit);
        return 1;
    }
    const unsigned x = fts_event_x(e), y = fts_event_y(e);
    if (x > FTS_MAX_X || y > FTS_MAX_Y) return 0;   // off the panel: a corrupt read, not a position
    t->x[id] = (uint16_t)x;
    t->y[id] = (uint16_t)y;
    t->type[id] = (uint8_t)fts_event_type(e);
    t->active |= bit;
    return 1;
}
#endif
