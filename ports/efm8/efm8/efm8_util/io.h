// Copyright 2018 jem@seethis.link
// Licensed under the MIT license (http://opensource.org/licenses/MIT)

#include <stdint.h>

// Useful defines for pin
#ifndef PIN0_bm
#  define PIN0_bm ((uint8_t)(1<<0))
#  define PIN1_bm ((uint8_t)(1<<1))
#  define PIN2_bm ((uint8_t)(1<<2))
#  define PIN3_bm ((uint8_t)(1<<3))
#  define PIN4_bm ((uint8_t)(1<<4))
#  define PIN5_bm ((uint8_t)(1<<5))
#  define PIN6_bm ((uint8_t)(1<<6))
#  define PIN7_bm ((uint8_t)(1<<7))
#endif

#ifndef P0_0
#  define P0_0 P0_B0
#  define P0_1 P0_B1
#  define P0_2 P0_B2
#  define P0_3 P0_B3
#  define P0_4 P0_B4
#  define P0_5 P0_B5
#  define P0_6 P0_B6
#  define P0_7 P0_B7

#  define P1_0 P1_B0
#  define P1_1 P1_B1
#  define P1_2 P1_B2
#  define P1_3 P1_B3
#  define P1_4 P1_B4
#  define P1_5 P1_B5
#  define P1_6 P1_B6
#  define P1_7 P1_B7

#  define P2_0 P2_B0
#  define P2_1 P2_B1
#  define P2_2 P2_B2
#  define P2_3 P2_B3
#  define P2_4 P2_B4
#  define P2_5 P2_B5
#  define P2_6 P2_B6
#  define P2_7 P2_B7

#  define P3_0 P3_B0
#  define P3_1 P3_B1
#  define P3_2 P3_B2
#  define P3_3 P3_B3
#  define P3_4 P3_B4
#  define P3_5 P3_B5
#  define P3_6 P3_B6
#  define P3_7 P3_B7

// port 4 not bit addressable
#endif

// Universal Bee
#if defined(EFM8UB1_DEVICE)
    #include "mcu/EFM8UB1/inc/SI_EFM8UB1_Defs.h"
    #include "mcu/EFM8UB1/inc/SI_EFM8UB1_Devices.h"
    #include "mcu/EFM8UB1/inc/SI_EFM8UB1_Register_Enums.h"
#elif defined(EFM8UB2_DEVICE)
    #include "mcu/EFM8UB2/inc/SI_EFM8UB2_Defs.h"
    #include "mcu/EFM8UB2/inc/SI_EFM8UB2_Devices.h"
    #include "mcu/EFM8UB2/inc/SI_EFM8UB2_Register_Enums.h"
#elif defined(EFM8UB3_DEVICE)
    #include "mcu/EFM8UB3/inc/SI_EFM8UB3_Defs.h"
    #include "mcu/EFM8UB3/inc/SI_EFM8UB3_Devices.h"
    #include "mcu/EFM8UB3/inc/SI_EFM8UB3_Register_Enums.h"
#elif defined(EFM8UB4_DEVICE)
    #include "mcu/EFM8UB4/inc/SI_EFM8UB3_Defs.h"
    #include "mcu/EFM8UB4/inc/SI_EFM8UB3_Devices.h"
    #include "mcu/EFM8UB4/inc/SI_EFM8UB3_Register_Enums.h"
#elif defined(EFM8LB1_DEVICE)
    #include "mcu/EFM8LB1/inc/SI_EFM8UB3_Defs.h"
    #include "mcu/EFM8LB1/inc/SI_EFM8UB3_Devices.h"
    #include "mcu/EFM8LB1/inc/SI_EFM8UB3_Register_Enums.h"
// Laser Bee
#elif defined(EFM8LB1_DEVICE)
    #include "mcu/EFM8LB1/inc/SI_EFM8LB1_Defs.h"
    #include "mcu/EFM8LB1/inc/SI_EFM8LB1_Devices.h"
    #include "mcu/EFM8LB1/inc/SI_EFM8LB1_Register_Enums.h"
// Sleepy Bee
#elif defined(EFM8SB1_DEVICE)
    #include "mcu/EFM8SB1/inc/SI_EFM8SB1_Defs.h"
    #include "mcu/EFM8SB1/inc/SI_EFM8SB1_Devices.h"
    #include "mcu/EFM8SB1/inc/SI_EFM8SB1_Register_Enums.h"
#elif defined(EFM8SB2_DEVICE)
    #include "mcu/EFM8SB2/inc/SI_EFM8SB2_Defs.h"
    #include "mcu/EFM8SB2/inc/SI_EFM8SB2_Devices.h"
    #include "mcu/EFM8SB2/inc/SI_EFM8SB2_Register_Enums.h"
// Busy Bee
#elif defined(EFM8BB1_DEVICE)
    #include "mcu/EFM8BB1/inc/SI_EFM8BB1_Defs.h"
    #include "mcu/EFM8BB1/inc/SI_EFM8BB1_Devices.h"
    #include "mcu/EFM8BB1/inc/SI_EFM8BB1_Register_Enums.h"
#elif defined(EFM8BB2_DEVICE)
    #include "mcu/EFM8BB2/inc/SI_EFM8BB2_Defs.h"
    #include "mcu/EFM8BB2/inc/SI_EFM8BB2_Devices.h"
    #include "mcu/EFM8BB2/inc/SI_EFM8BB2_Register_Enums.h"
#elif defined(EFM8BB3_DEVICE)
    #include "mcu/EFM8BB3/inc/SI_EFM8BB3_Defs.h"
    #include "mcu/EFM8BB3/inc/SI_EFM8BB3_Devices.h"
    #include "mcu/EFM8BB3/inc/SI_EFM8BB3_Register_Enums.h"
#else
#  error "Device family not defined"
#endif
