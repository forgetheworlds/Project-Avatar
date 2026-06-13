Building an **autonomous, sub-250g FPV water gun drone** is one of the most mechanically and computationally complex micro-UAV projects attempted by the maker community. Merging open-source autonomy with FPV and a liquid payload requires aggressive weight optimization and deep physics considerations. `[85][86][87][88][89][90]`

The collective findings, successes, and failures documented across **Reddit, [YouTube](https://www.youtube.com/watch?v=bmtrZl9fJZE), and Hackaday** detail how to successfully execute this unique build. `[79][80][81][82][83][84]`

---

🛠️ The Sub-250g Hardware Stack 

To keep the entire craft under the legal **250-gram limit (including battery, water gun payload, and liquid)**, developers rely on an ultra-light long-range or freestyle platform: `[73][74][75][76][77][78]`

* **Frame/Motors**: A lightweight **3-inch to 3.5-inch carbon frame** (e.g., inspired by platforms like the DeepSpace Seeker or Roc) paired with high-efficiency **1404 or 1505 brushless motors**. `[67][68][69][70][71][72]`
* **Flight Controller (FC)**: A compact **All-In-One (AIO) board** running **ArduPilot** rather than Betaflight. ArduPilot is necessary for handling the complex script-guided automation, mission planning, and sensor inputs needed for autonomy. `[61][62][63][64][65][66]`

* **Video/FPV**: A lightweight digital system like the **[DJI O4 Air Unit Lite Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462810451589573,imageDocid:10233482140463536396,gpcid:7525468607673077004,headlineOfferDocid:18178869802793163056,catalogid:17493906027872825602,productDocid:14486168536047762769,rds:PC_7525468607673077004%7CPROD_PC_7525468607673077004&q=product&sa=X&ved=2ahUKEwi78suth-WUAxXNlYkEHTzUMhcQxa4PeggIAggACCIQDg)** or
  [Walksnail Avatar Nano Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:1780943035250195515,gpcid:11789474043422635054,headlineOfferDocid:2759140927729078567,catalogid:92081539233043771,productDocid:8730620218726607545,rds:PC_11789474043422635054%7CPROD_PC_11789474043422635054&q=product&sa=X&ved=2ahUKEwi78suth-WUAxXNlYkEHTzUMhcQxa4PeggIAggACCIQEA) to keep visual tracking clear while saving precious grams. `[55][56][57][58][59][60]`
* **Telemetry Link**: Utilizing **ExpressLRS AirPort**, a feature that transforms standard ELRS control links into a transparent bi-directional serial data connection. This allows live MAVLink telemetry and command overrides from a ground control station without adding a heavy secondary radio module. `[49][50][51][52][53][54]`
*

---

💧 The Water Gun Payload Design 

Standard motorized water toys are far too heavy. Maker community successes lean heavily on micro-fluidics and 3D printing: `[43][44][45][46][47][48]`

* **The Pump**: A 3V to 5V **micro diaphragm pump** or mini centrifugal pump weighing under 15 grams. `[37][38][39][40][41][42]`
* **The Reservoir**: Custom 3D-printed PETG or TPU ultra-thin fluid tanks (typically capped at **30ml to 50ml of capacity**). Water weighs exactly 1 gram per milliliter; a 50ml payload eats up 50g of your total budget. 

* **Actuation**: The pump is wired directly through a micro **MOSFET switch** or miniature relay tied to a spare PWM pad on the
  [Flight Controller Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462813182336616,imageDocid:10367704602595881923,gpcid:14536932249042217427,headlineOfferDocid:463571303173976950,catalogid:6281494607304012194,productDocid:18085001822763243501,rds:PC_14536932249042217427%7CPROD_PC_14536932249042217427&q=product&sa=X&ved=2ahUKEwi78suth-WUAxXNlYkEHTzUMhcQxa4PeggIAggACC4QCg)
, mapping the "trigger" to an ArduPilot servo command. `[31][32][33][34][35][36]`
*

---

🤖 Implementing Autonomy 

True autonomy on a micro-drone cannot support a heavy onboard

[Raspberry Pi 4/5 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462858662667794,imageDocid:12829131069042921200,gpcid:17916862898082255347,headlineOfferDocid:11040578484891938393,catalogid:10112476156642094252,productDocid:7013151915891953130,rds:PC_17916862898082255347%7CPROD_PC_17916862898082255347&q=product&sa=X&ved=2ahUKEwi78suth-WUAxXNlYkEHTzUMhcQxa4PeggIAggACDUQAg) or

[Jetson Nano Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462828031222921,imageDocid:6992135493104194581,gpcid:12165231684686929574,headlineOfferDocid:2369337976869997141,catalogid:2346485905485317635,productDocid:3929344143691015474,rds:PC_12165231684686929574%7CPROD_PC_12165231684686929574&q=product&sa=X&ved=2ahUKEwi78suth-WUAxXNlYkEHTzUMhcQxa4PeggIAggACDUQBA)

. Creators split the computation using a **Distributed AI architecture**: `[25][26][27][28][29][30]`

1. **Onboard Camera & Transmitter**: The FPV camera streams live video back to the ground.
2. **Ground Station Computer Vision**: A laptop or ground station captures the FPV feed feed via a UVC receiver. An **OpenCV or YOLOv8 script** processes the image in real-time to detect targets (e.g., pests, targets, or specific objects) and calculate error offsets from the crosshair.
3. **Autonomous Loop**: The ground computer automatically transmits precision yaw/pitch adjustments back to the drone via **ExpressLRS telemetry (MAVLink)**, instructing ArduPilot to align and trigger the pump relay once the target is locked. `[19][20][21][22][23][24]`

---

❌ Critical Failures & Lessons Learned 

1. The Sloshing Effect (The Death of Flight Stability) 

* **The Failure**: Early attempts using basic open water boxes caused the drone to instantly wobble and crash as soon as it pitched forward. Liquid movement shifts the center of gravity dynamically, causing the flight controller's PID loop to overcorrect and freak out.
* **The Lesson**: Tanks must feature internal **baffles** (walls with tiny holes) or use flexible **medical fluid bladders** that collapse as fluid is spent, eliminating free-surface sloshing entirely. 
*

2. Newton’s Third Law (Water Jet Recoil) 

* **The Failure**: Spraying a powerful stream of water forces the micro-drone backwards. On a sub-250g quad, this sudden kinetic force pushes the front down, causing the drone to unintentionally dive or break target lock.
* **The Lesson**: The water nozzle must be mounted as close to the **true Center of Gravity (CoG)** as possible, or the ArduPilot PID profile must be tuned aggressively to compensate for the forward counter-thrust. 

3. Voltage Sags and "Brownouts" 

* **The Failure**: Tapping the drone's main flight battery to power the electric water pump causes sudden voltage drops when the pump is triggered, causing the
  [Flight Controller Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462810922631197,imageDocid:10498258599431234460,gpcid:9595870912009561613,headlineOfferDocid:9607629180334170700,catalogid:12099736281028146207,productDocid:9259348397750090193,rds:PC_9595870912009561613%7CPROD_PC_9595870912009561613&q=product&sa=X&ved=2ahUKEwi78suth-WUAxXNlYkEHTzUMhcQxa4PeggIAggACEIQAg) to reboot mid-air.
* **The Lesson**: Incorporate a dedicated **micro step-up/down voltage regulator (BEC)** to isolate the flight electronics from the pump circuit, or run a tiny auxiliary 1S battery specifically for the payload. `[13][14][15][16][17][18]`

4. The Weight Math Trap 

* **The Failure**: Over-engineering the frame. Adding heavy pan-and-tilt servos to aim the water gun dynamically pushes the dry weight past 200g, leaving room for only a few drops of water.
* **The Lesson**: Fix the nozzle strictly to the front of the drone frame. Let the entire autonomous drone act as the gimbal by using its own yaw and pitch axes to aim at the target. `[7][8][9][10][11][12]`

---

🏆 Key Success Factors 

* **Aggressive Weight Budgeting**: Aim for a "dry weight" (drone without water payload) of **under 175-180 grams**. This preserves a crucial 70g margin for your custom tank, pump, and water.
* **Conformal Coating**: Water bounces back and mists in mid-air. Treat all exposed circuit boards, ESCs, and AIO pins with silicone **conformal coating** (like MG Chemicals 422B) to prevent immediate short circuits when shooting targets. `[1][2][3][4][5][6]`

If you are beginning this build, would you like to focus first on optimizing the **physical 3D printed fluid dynamics / pump mechanics**, or would you prefer help writing the **OpenCV ground station target-tracking script**? 

Copy

# Share public link

This public link is valid for 7 days and shares a thread, including any personal information you added. This link or copies made by others cannot be deleted. If you share with third parties, their policies apply.

Can’t copy the link right now. Try again later.

Facebook

Gmail

X

Reddit

WhatsApp

Good response

Bad response

Saved time

Clear

Helpful

Comprehensive

Other

Incorrect

Inappropriate

Not working

Unhelpful

Other

A copy of this chat, including the images and video, will be included with your feedback

A copy of this chat will be included with your feedback

Your feedback will include a copy of this chat and the image from your search

Your feedback will include a copy of this chat, any links you shared, and the image from your search.

Thanks for letting us know

Google may use account and system data to understand your feedback and improve our services, subject to our [Privacy Policy](https://policies.google.com/privacy) and [Terms of Service](https://policies.google.com/terms). For legal issues, [make a legal removal request](https://support.google.com/legal/answer/3110420).

---

## Sources:

[1] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[2] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[3] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[4] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[5] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[6] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[7] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[8] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[9] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[10] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[11] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[12] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[13] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[14] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[15] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[16] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[17] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[18] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[19] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[20] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[21] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[22] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[23] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[24] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[25] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[26] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[27] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[28] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[29] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[30] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[31] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[32] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[33] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[34] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[35] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[36] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[37] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[38] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[39] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[40] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[41] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[42] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[43] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[44] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[45] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[46] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[47] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[48] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[49] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[50] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[51] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[52] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[53] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[54] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[55] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[56] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[57] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[58] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[59] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[60] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[61] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[62] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[63] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[64] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[65] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[66] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[67] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[68] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[69] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[70] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[71] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[72] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[73] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[74] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[75] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[76] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[77] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[78] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[79] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[80] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[81] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[82] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[83] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[84] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

[85] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=3

[86] The Best sub 250g 4" FPV Drone? DeepSpace Roc 4. Opens in new tab.  
https://www.youtube.com/watch?v=bmtrZl9fJZE

[87] Water Gun | Hackaday. Opens in new tab.  
https://hackaday.com/tag/water-gun/

[88] About to build my first FPV drone! 3.5" sub-250g setting - Reddit. Opens in new tab.  
https://www.reddit.com/r/fpv/comments/1kp4cja/about_to_build_my_first_fpv_drone_35_sub250g/

[89] Building autonomous drones. : r/diydrones - Reddit. Opens in new tab.  
https://www.reddit.com/r/diydrones/comments/1counqw/building_autonomous_drones/

[90] drone that sprays liquids - Reddit. Opens in new tab.  
https://www.reddit.com/r/drones/comments/1b5tsq7/drone_that_sprays_liquids/

