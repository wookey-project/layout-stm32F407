#!/usr/bin/env python3
#
# This file is used in order to generate header files for userspace
# drivers based on the layout json file given in argument.
# This permit to generate the following information for each mappable device:
# - address
# - size
# - IRQ list
# - GPIO couple (pin/port) list

# each device has its own file header (i.e. usart1.h, usb-otg-fs.h and so on),
# containing a static const structure named with the device name with
# the following pattern: <devname>_dev_infos (e.g. usart1_dev_infos).
#
# Generated headers can be included concurrently. They do not require any
# specific permission and do not host any executable content.

import sys
import os
# with collection, we keep the same device order as the json file
import json, collections
import re

if len(sys.argv) != 3:
    print("usage: ", sys.argv[0], "<outdir> <filename.json>\n");
    sys.exit(1);

# mode is C or ADA
outdir = sys.argv[1];
filename = sys.argv[2];

########################################################
# C file header and footer
########################################################

# print type:
c_header = """/*
 *
 * Copyright 2018 The wookey project team <wookey@ssi.gouv.fr>
 *   - Ryad     Benadjila
 *   - Arnauld  Michelizza
 *   - Mathieu  Renard
 *   - Philippe Thierry
 *   - Philippe Trebuchet
 *
 * This package is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published
 * the Free Software Foundation; either version 2.1 of the License, or (at
 * ur option) any later version.
 *
 * This package is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE. See the GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License along
 * with this package; if not, write to the Free Software Foundation, Inc., 51
 * Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
 *
 * This file has been generated by devheader.py from a Tataouine SDK Json layout file
 *
 */
"""

c_definition = """

#include "libc/types.h"
#include "libc/syscall.h"


/*
** This file defines the valid adress ranges where devices are mapped.
** This allows the kernel to check that device registration requests correct
** mapping.
**
** Of course these informations are SoC specific
** This file may be completed by a bord specific file for board devices
*/

/*!
** @brief Structure defining the STM32 device map
**
** This table is based on doc STMicro RM0090 Reference manual memory map
** Only devices that may be registered by userspace are mapped here
**
** See #soc_devices_list
*/

struct user_driver_device_gpio_infos {
    uint8_t    port;
    uint8_t    pin;
};

struct user_driver_device_dma_infos {
    uint8_t    channel;
    uint8_t    stream;
};

struct user_driver_device_infos {
    physaddr_t address;    /**< Device MMIO base address */
    uint32_t   size;       /**< Device MMIO mapping size */
    /** GPIO informations of the device (pin, port) */
    struct user_driver_device_gpio_infos gpios[18];
};


""";


c_footer= """

#endif
""";

if not os.path.exists(outdir):
    os.makedirs(outdir);

if not os.path.isfile(filename):
    print(u'unable to open {}'.filename);
    exit(0);

with open(filename, "r") as jsonfile:
    data = json.load(jsonfile, object_pairs_hook=collections.OrderedDict);



def generate_c():
    # max number of GPIOs per dictionary entry
    max_gpio_num = 18; # 18 is requested by ETH_MAC

    # structure definition
    with open(os.path.join(outdir, 'devinfo.h'), "w") as devinfofile:
            devinfofile.write(c_header);
            devinfofile.write("#ifndef DEVINFO_H_\n");
            devinfofile.write("# define DEVINFO_H_\n");
            devinfofile.write(c_definition);
            devinfofile.write("#endif/*!DEVINFO_H_*/\n");

    for device in data:
        dev = device["name"];
        device_c_name = dev.replace("-", "_");
        if device["size"] == "0" and device["type"] == "block":
            # we do not generate headers for unmappable block device (e.g. DMA)
            continue;
        devfilename = device_c_name + ".h";
        devheadername = device_c_name.upper() + "_H_";

        with open(os.path.join(outdir, devfilename), "w") as devfile:
            # header (license)
            devfile.write(c_header);
            # preprocessing and inclusion
            devfile.write("#ifndef %s\n" % devheadername);
            devfile.write("# define %s\n" % devheadername);
            devfile.write("\n#include \"generated/devinfo.h\"\n\n");

            devfile.write("# define %s_BASE %s\n" % (device_c_name.upper(), device["address"]));

            if device["type"] == "block":
                # generating defines for IRQ values
                if 'irqs' in device:
                    irqs = device["irqs"];
                    for irq in irqs:
                        if irq["value"] != 0:
                            devfile.write("#define %s %s\n" % (irq["name"], irq["value"]));

            if 'gpios' in device:
                gpios = device["gpios"];
                devfile.write("/* naming indexes in structure gpios[] table */\n");
                for index, gpio in enumerate(gpios):
                    devfile.write("#define %s %d\n" % (gpio["name"], index));

            if 'dmas' in device:
                dmas = device["dmas"];
                devfile.write("#define %s %s\n" % (dmas["controler_name"], dmas["controler_id"]));
                devfile.write("/* naming indexes in structure dmas[] table */\n");
                dma_info_list = dmas["dma"];
                for dma_info in dma_info_list:
                    devfile.write("#define %s %s\n" % (dma_info["name"], dma_info["value"]));

            # global variable declaration
            devfile.write("\nstatic const struct user_driver_device_infos %s_dev_infos = {\n" % device_c_name);
            # device address
            devfile.write("    .address = %s,\n" % device["address"]);
            # device size
            devfile.write("    .size    = %s,\n" % device["size"]);

            # device gpios
            devfile.write("    .gpios = {\n");
            if 'gpios' in device:
                gpios = device["gpios"];
                for gpio in gpios[0:]:
                    devfile.write("      { %s, %s }, /* %s */\n" % (gpio["port"], gpio["pin"], gpio["name"]));
                if len(gpios) < max_gpio_num:
                    for i in range(len(gpios), max_gpio_num):
                        devfile.write("      { 0, 0 },\n");

            else:
                for i in range(1,13):
                    devfile.write("      { 0, 0 },\n");

            devfile.write("    }\n");
            devfile.write("};\n");

            # closing preprocessing
            devfile.write(c_footer);


generate_c();
