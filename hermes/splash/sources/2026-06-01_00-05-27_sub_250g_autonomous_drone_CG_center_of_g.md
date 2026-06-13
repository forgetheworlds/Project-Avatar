To achieve stable flight, a sub-250g autonomous drone must have its **Center of Gravity (CG) perfectly centered** at the intersection of the motor diagonals, matching the physical center of thrust. For sub-250g builds, even a **2mm to 5mm offset** forces motors to work unevenly, drastically reducing flight times and degrading autonomous navigation accuracy. 

Here is how to calculate, balance, and place your payload components for a balanced build. 

---

1. Calculate the Target CG 

The ideal CG is the geometric center of your propulsion system. 

* **Square Frames:** Draw diagonal lines from the center of Motor 1 to Motor 4, and Motor 2 to Motor 3. The intersection point is your target CG. 
* **Asymmetrical Frames (Deadcat/H):** Use a weighted average of the motor positions. Calculate the midpoint of the front two motors and the midpoint of the rear two motors. The target CG lies along the centerline, spaced proportionally based on the front-to-rear motor distance ratio. 
*

---

2. Formulate the Component Balance 

To calculate the exact placement of your payload, treat the drone as a 1D or 2D lever system using the torque balance formula: 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mo largeop="true" movablelimits="true">∑</mo><mo>(</mo><msub><mi>m</mi><mi>i</mi></msub><mo>×</mo><msub><mi>d</mi><mi>i</mi></msub><mo>)</mo><mo>=</mo><mn>0</mn></mrow><annotation encoding="text/plain">sum of open paren m sub i cross d sub i close paren equals 0</annotation></semantics></math> --> ∑(mi×di)=0sum of open paren m sub i cross d sub i close paren equals 0

Where: 

* 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>m</mi><mi>i</mi></msub><annotation encoding="text/plain">m sub i</annotation></semantics></math> --> mim sub i

= Mass of an individual component (grams)
* 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>d</mi><mi>i</mi></msub><annotation encoding="text/plain">d sub i</annotation></semantics></math> --> did sub i

= Distance from the target CG point (mm). Components behind or to the left of the CG use negative distances; components in front or to the right use positive distances. 
*

Example Calculation (Pitch Axis) 

If your bare frame, motors, and stack weigh and are perfectly centered (

), you must balance a camera payload and a flight battery: 

* **Camera Payload (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>m</mi><mn>1</mn></msub><annotation encoding="text/plain">m sub 1</annotation></semantics></math> --> m1m sub 1

):**  mounted forward at

* **Battery Pack (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>m</mi><mn>2</mn></msub><annotation encoding="text/plain">m sub 2</annotation></semantics></math> --> m2m sub 2

):**  mounted toward the rear at an unknown distance (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>d</mi><mn>2</mn></msub><annotation encoding="text/plain">d sub 2</annotation></semantics></math> --> d2d sub 2

). 
*

Set up the equation to find the required battery placement (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>d</mi><mn>2</mn></msub><annotation encoding="text/plain">d sub 2</annotation></semantics></math> --> d2d sub 2

):

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mo>(</mo><mn>140</mn><mo>×</mo><mn>0</mn><mo>)</mo><mo>+</mo><mo>(</mo><mn>25</mn><mo>×</mo><mn>35</mn><mo>)</mo><mo>+</mo><mo>(</mo><mn>75</mn><mo>×</mo><msub><mi>d</mi><mn>2</mn></msub><mo>)</mo><mo>=</mo><mn>0</mn></mrow><annotation encoding="text/plain">open paren 140 cross 0 close paren plus open paren 25 cross 35 close paren plus open paren 75 cross d sub 2 close paren equals 0</annotation></semantics></math> --> (140×0)+(25×35)+(75×d2)=0open paren 140 cross 0 close paren plus open paren 25 cross 35 close paren plus open paren 75 cross d sub 2 close paren equals 0

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mn>875</mn><mo>+</mo><mn>75</mn><msub><mi>d</mi><mn>2</mn></msub><mo>=</mo><mn>0</mn></mrow><annotation encoding="text/plain">875 plus 75 d sub 2 equals 0</annotation></semantics></math> --> 875+75d2=0875 plus 75 d sub 2 equals 0

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mn>75</mn><msub><mi>d</mi><mn>2</mn></msub><mo>=</mo><mn>-875</mn></mrow><annotation encoding="text/plain">75 d sub 2 equals negative 875</annotation></semantics></math> --> 75d2=-87575 d sub 2 equals negative 875

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>d</mi><mn>2</mn></msub><mo>=</mo><mn>-11.67</mn><mtext> mm</mtext></mrow><annotation encoding="text/plain">d sub 2 equals negative 11.67  mm</annotation></semantics></math> --> d2=-11.67 mmd sub 2 equals negative 11.67  mm

The battery must be placed exactly ** behind the target CG** to counteract the front camera weight. 

---

3. Arrange Component Placement 

Sub-250g drones have limited surface area. Use this spatial priority list when mounting components: `[19][20][21]`

* **Flight Controller (FC) / IMU:** Place this **exactly at the target CG**. Autonomous firmware (like ArduPilot or INAV) assumes the gyro sits at the rotation center to prevent control loop calculation errors. `[16][17][18]`
* **Battery (Heavy Variable):** Mount the battery on adjustable rails or hook-and-loop straps. Because it constitutes up to of a sub-250g drone's total weight, moving it slightly is your primary method for fine-tuning balance. 
* **Autonomous Payload:** Place cameras, optical flow sensors, and companion computers (e.g., Raspberry Pi Zero) first. Balance their fixed weights by shifting the battery in the opposite direction. `[13][14][15]`
* **GPS / Compass Module:** Mount high and away from high-current power leads to avoid magnetic interference. Its lightweight footprint ( to
  
  
) has a minimal impact on CG, but it should still sit along the longitudinal centerline. `[10][11][12]`

---

4. Verify Physical Balance `[7][8][9]`

Never rely solely on software calculations. Physically test your balance before the first flight: 

* **The Pivot Test:** Place a fine-tipped object (like an inverted screwdriver or a balancing jig) exactly under the frame's calculated target CG point. The drone must remain completely level across both the pitch and roll axes. `[4][5][6]`
* **The Suspension Test:** Tie a thin string to the exact intersection of the motor diagonals. Hang the drone. If the frame tilts in any direction, relocate the battery until the prop nuts sit entirely parallel to the ground. 

---

✅ Final Target Summary 

The final build must satisfy the absolute balance condition relative to the geometric center: `[1][2][3]`

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mtext>Total Offset</mtext><mo>=</mo><mfrac><mrow><mo largeop="true" movablelimits="true">∑</mo><mo>(</mo><msub><mi>m</mi><mi>i</mi></msub><mo>×</mo><msub><mi>d</mi><mi>i</mi></msub><mo>)</mo></mrow><mrow><mo largeop="true" movablelimits="true">∑</mo><msub><mi>m</mi><mi>i</mi></msub></mrow></mfrac><mo>=</mo><mn>0</mn><mtext> mm</mtext></mrow><annotation encoding="text/plain">Total Offset equals the fraction with numerator sum of open paren m sub i cross d sub i close paren and denominator sum of m sub i end-fraction equals 0  mm</annotation></semantics></math> --> Total Offset=∑(mi×di)∑mi=0 mmTotal Offset equals the fraction with numerator sum of open paren m sub i cross d sub i close paren and denominator sum of m sub i end-fraction equals 0  mm

Achieving a calculated and verified offset of ** ** ensures that your autonomous tuning variables (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>P</mi><mi>I</mi><mi>D</mi><mi>S</mi></mrow><annotation encoding="text/plain">cap P cap I cap D cap S</annotation></semantics></math> --> PIDScap P cap I cap D cap S

) operate symmetrically, providing predictable loiter, waypoint navigation, and wind resistance. 

---

If you want to refine your layout, tell me: 

* What **frame size/style** are you using?
* What is the **exact weight** of your camera or companion computer payload?
* Are you planning to mount the battery on the **top or bottom** of the frame? 

I can provide a tailored layout strategy or calculate the exact millimeter placements for your components. 

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

[1] A Gravity-Height Fusion Planning, Control Method Based on Deep Reinforcement Learning for Small Celestial Body Exploration Robots. Opens in new tab.  
https://www.sciencedirect.com/science/article/pii/S027311772600431X

[2] Want To INAV Your Quad? Read These Frequently Asked Questions – NoirFPV. Opens in new tab.  
https://noirfpv.com/inav-frequently-asked-questions/

[3] Robotics Projects | Autonomous Pi-Drone – Razbotics. Opens in new tab.  
https://razbotics.wordpress.com/2019/11/29/autonomous-pi-drone/

[4] A Gravity-Height Fusion Planning, Control Method Based on Deep Reinforcement Learning for Small Celestial Body Exploration Robots. Opens in new tab.  
https://www.sciencedirect.com/science/article/pii/S027311772600431X

[5] Want To INAV Your Quad? Read These Frequently Asked Questions – NoirFPV. Opens in new tab.  
https://noirfpv.com/inav-frequently-asked-questions/

[6] Robotics Projects | Autonomous Pi-Drone – Razbotics. Opens in new tab.  
https://razbotics.wordpress.com/2019/11/29/autonomous-pi-drone/

[7] A Gravity-Height Fusion Planning, Control Method Based on Deep Reinforcement Learning for Small Celestial Body Exploration Robots. Opens in new tab.  
https://www.sciencedirect.com/science/article/pii/S027311772600431X

[8] Want To INAV Your Quad? Read These Frequently Asked Questions – NoirFPV. Opens in new tab.  
https://noirfpv.com/inav-frequently-asked-questions/

[9] Robotics Projects | Autonomous Pi-Drone – Razbotics. Opens in new tab.  
https://razbotics.wordpress.com/2019/11/29/autonomous-pi-drone/

[10] A Gravity-Height Fusion Planning, Control Method Based on Deep Reinforcement Learning for Small Celestial Body Exploration Robots. Opens in new tab.  
https://www.sciencedirect.com/science/article/pii/S027311772600431X

[11] Want To INAV Your Quad? Read These Frequently Asked Questions – NoirFPV. Opens in new tab.  
https://noirfpv.com/inav-frequently-asked-questions/

[12] Robotics Projects | Autonomous Pi-Drone – Razbotics. Opens in new tab.  
https://razbotics.wordpress.com/2019/11/29/autonomous-pi-drone/

[13] A Gravity-Height Fusion Planning, Control Method Based on Deep Reinforcement Learning for Small Celestial Body Exploration Robots. Opens in new tab.  
https://www.sciencedirect.com/science/article/pii/S027311772600431X

[14] Want To INAV Your Quad? Read These Frequently Asked Questions – NoirFPV. Opens in new tab.  
https://noirfpv.com/inav-frequently-asked-questions/

[15] Robotics Projects | Autonomous Pi-Drone – Razbotics. Opens in new tab.  
https://razbotics.wordpress.com/2019/11/29/autonomous-pi-drone/

[16] A Gravity-Height Fusion Planning, Control Method Based on Deep Reinforcement Learning for Small Celestial Body Exploration Robots. Opens in new tab.  
https://www.sciencedirect.com/science/article/pii/S027311772600431X

[17] Want To INAV Your Quad? Read These Frequently Asked Questions – NoirFPV. Opens in new tab.  
https://noirfpv.com/inav-frequently-asked-questions/

[18] Robotics Projects | Autonomous Pi-Drone – Razbotics. Opens in new tab.  
https://razbotics.wordpress.com/2019/11/29/autonomous-pi-drone/

[19] A Gravity-Height Fusion Planning, Control Method Based on Deep Reinforcement Learning for Small Celestial Body Exploration Robots. Opens in new tab.  
https://www.sciencedirect.com/science/article/pii/S027311772600431X

[20] Want To INAV Your Quad? Read These Frequently Asked Questions – NoirFPV. Opens in new tab.  
https://noirfpv.com/inav-frequently-asked-questions/

[21] Robotics Projects | Autonomous Pi-Drone – Razbotics. Opens in new tab.  
https://razbotics.wordpress.com/2019/11/29/autonomous-pi-drone/

