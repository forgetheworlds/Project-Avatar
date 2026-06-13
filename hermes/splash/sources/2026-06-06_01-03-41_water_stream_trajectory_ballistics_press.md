The maximum horizontal projectile distance of a water stream fired from a drone can be calculated using **ballistic trajectory equations combined with fluid mechanics**. The maximum theoretical horizontal distance (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>R</mi><annotation encoding="text/plain">cap R</annotation></semantics></math> --> Rcap R

) a water droplet can travel in a vacuum is given by the formula

, where

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>v</mi><mn>0</mn></msub><annotation encoding="text/plain">v sub 0</annotation></semantics></math> --> v0v sub 0 is the nozzle exit velocity,

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>θ</mi><annotation encoding="text/plain">theta</annotation></semantics></math> --> θtheta is the launch angle, and

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>g</mi><annotation encoding="text/plain">g</annotation></semantics></math> --> gg is gravity (

). 

However, for a real-world drone application, **aerodynamic drag breaks the water stream into droplets**, rapidly slowing it down. Calculating the actual trajectory requires accounting for pressure drops, nozzle mechanics, and pump constraints. `[13][14][15]`

---

1. Calculate Nozzle Exit Velocity 

To find out how far the water will go, you must first determine the velocity (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>v</mi><mn>0</mn></msub><annotation encoding="text/plain">v sub 0</annotation></semantics></math> --> v0v sub 0

) at which it leaves the nozzle. This depends entirely on the flow rate (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>Q</mi><annotation encoding="text/plain">cap Q</annotation></semantics></math> --> Qcap Q

) and the nozzle orifice size (cross-sectional area,

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>A</mi><annotation encoding="text/plain">cap A</annotation></semantics></math> --> Acap A

). 

*

* **Nozzle Area (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>A</mi><annotation encoding="text/plain">cap A</annotation></semantics></math> --> Acap A

):**
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>A</mi><mo>=</mo><mfrac><mrow><mi>π</mi><mo>⋅</mo><msup><mi>d</mi><mn>2</mn></msup></mrow><mn>4</mn></mfrac></mrow><annotation encoding="text/plain">cap A equals the fraction with numerator pi center dot d squared and denominator 4 end-fraction</annotation></semantics></math> --> A=π⋅d24cap A equals the fraction with numerator pi center dot d squared and denominator 4 end-fraction

*(Where
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>d</mi><annotation encoding="text/plain">d</annotation></semantics></math> --> dd is the internal diameter of the nozzle orifice in meters)*

* **Exit Velocity (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>v</mi><mn>0</mn></msub><annotation encoding="text/plain">v sub 0</annotation></semantics></math> --> v0v sub 0

):**
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>v</mi><mn>0</mn></msub><mo>=</mo><mfrac><mi>Q</mi><mi>A</mi></mfrac></mrow><annotation encoding="text/plain">v sub 0 equals the fraction with numerator cap Q and denominator cap A end-fraction</annotation></semantics></math> --> v0=QAv sub 0 equals the fraction with numerator cap Q and denominator cap A end-fraction

*(Where
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>Q</mi><annotation encoding="text/plain">cap Q</annotation></semantics></math> --> Qcap Q is the volumetric flow rate in
  
  
)* `[10][11][12]`

*

2. Calculate Pressure Drop Across Nozzle 

The pressure required at the nozzle tip (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>P</mi><mtext>nozzle</mtext></msub><annotation encoding="text/plain">cap P sub nozzle end-sub</annotation></semantics></math> --> Pnozzlecap P sub nozzle end-sub

) to achieve this exit velocity is derived from Bernoulli’s principle (assuming an efficient, smooth nozzle coefficient to

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mn>0.98</mn><annotation encoding="text/plain">0.98</annotation></semantics></math> --> 0.980.98

): 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>P</mi><mtext>nozzle</mtext></msub><mo>=</mo><mfrac><mn>1</mn><mn>2</mn></mfrac><mo>⋅</mo><mi>ρ</mi><mo>⋅</mo><msup><mrow><mo>(</mo><mfrac><msub><mi>v</mi><mn>0</mn></msub><msub><mi>C</mi><mi>d</mi></msub></mfrac><mo>)</mo></mrow><mn>2</mn></msup></mrow><annotation encoding="text/plain">cap P sub nozzle end-sub equals one-half center dot rho center dot open paren the fraction with numerator v sub 0 and denominator cap C sub d end-fraction close paren squared</annotation></semantics></math> --> Pnozzle=12⋅ρ⋅(v0Cd)2cap P sub nozzle end-sub equals one-half center dot rho center dot open paren the fraction with numerator v sub 0 and denominator cap C sub d end-fraction close paren squared

*

* 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>ρ</mi><annotation encoding="text/plain">rho</annotation></semantics></math> --> ρrho

= Density of water (
  
  
)

* 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>C</mi><mi>d</mi></msub><annotation encoding="text/plain">cap C sub d</annotation></semantics></math> --> Cdcap C sub d

= Nozzle discharge coefficient `[7][8][9]`

*

3. Total System Pressure Drop (Drone Constraints) 

Because the pump is often on the ground or distributed across a long vertical hose lifting water to the drone, you must calculate the total pressure the pump needs to deliver (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>P</mi><mtext>pump</mtext></msub><annotation encoding="text/plain">cap P sub pump end-sub</annotation></semantics></math> --> Ppumpcap P sub pump end-sub

): 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>P</mi><mtext>pump</mtext></msub><mo>=</mo><msub><mi>P</mi><mtext>nozzle</mtext></msub><mo>+</mo><mi>Δ</mi><msub><mi>P</mi><mtext>friction</mtext></msub><mo>+</mo><mi>Δ</mi><msub><mi>P</mi><mtext>elevation</mtext></msub></mrow><annotation encoding="text/plain">cap P sub pump end-sub equals cap P sub nozzle end-sub plus cap delta cap P sub friction end-sub plus cap delta cap P sub elevation end-sub</annotation></semantics></math> --> Ppump=Pnozzle+ΔPfriction+ΔPelevationcap P sub pump end-sub equals cap P sub nozzle end-sub plus cap delta cap P sub friction end-sub plus cap delta cap P sub elevation end-sub

*

* **Elevation Pressure Drop (
  
  
):** The pressure lost purely by fighting gravity to lift water to the drone's altitude (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>h</mi><annotation encoding="text/plain">h</annotation></semantics></math> --> hh

).
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>Δ</mi><msub><mi>P</mi><mtext>elevation</mtext></msub><mo>=</mo><mi>ρ</mi><mo>⋅</mo><mi>g</mi><mo>⋅</mo><mi>h</mi></mrow><annotation encoding="text/plain">cap delta cap P sub elevation end-sub equals rho center dot g center dot h</annotation></semantics></math> --> ΔPelevation=ρ⋅g⋅hcap delta cap P sub elevation end-sub equals rho center dot g center dot h

* **Friction Pressure Drop (
  
  
):** The friction loss inside the hose leading to the drone, calculated using the Darcy-Weisbach equation:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>Δ</mi><msub><mi>P</mi><mtext>friction</mtext></msub><mo>=</mo><mi>f</mi><mo>⋅</mo><mfrac><mi>L</mi><mi>D</mi></mfrac><mo>⋅</mo><mfrac><mrow><mi>ρ</mi><mo>⋅</mo><msubsup><mi>v</mi><mtext>hose</mtext><mn>2</mn></msubsup></mrow><mn>2</mn></mfrac></mrow><annotation encoding="text/plain">cap delta cap P sub friction end-sub equals f center dot the fraction with numerator cap L and denominator cap D end-fraction center dot the fraction with numerator rho center dot v sub hose end-sub squared and denominator 2 end-fraction</annotation></semantics></math> --> ΔPfriction=f⋅LD⋅ρ⋅vhose22cap delta cap P sub friction end-sub equals f center dot the fraction with numerator cap L and denominator cap D end-fraction center dot the fraction with numerator rho center dot v sub hose end-sub squared and denominator 2 end-fraction

*(Where
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>f</mi><annotation encoding="text/plain">f</annotation></semantics></math> --> ff is the friction factor,
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>L</mi><annotation encoding="text/plain">cap L</annotation></semantics></math> --> Lcap L is hose length,
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>D</mi><annotation encoding="text/plain">cap D</annotation></semantics></math> --> Dcap D is hose diameter, and
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>v</mi><mtext>hose</mtext></msub><annotation encoding="text/plain">v sub hose end-sub</annotation></semantics></math> --> vhosev sub hose end-sub is water velocity inside the hose)* `[4][5][6]`

*

4. Estimate Real-World Projectile Distance 

In standard ballistics, a

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mn>45</mn><mo>∘</mo></msup><annotation encoding="text/plain">45 raised to the composed with power</annotation></semantics></math> --> 45∘45 raised to the composed with power angle yields the maximum distance. For water streams, air resistance converts the solid stream into a fine mist, severely reducing range. `[1][2][3]`

An accurate calculation requires step-by-step numerical integration of drag (

). For a quick engineering estimation of effective stream reach, firefighters use **Blair's formula** or modified trajectory estimates: 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mi>R</mi><mtext>effective</mtext></msub><mo>≈</mo><mn>0.05</mn><mo>⋅</mo><msub><mi>P</mi><mtext>nozzle</mtext></msub><mtext> (in psi)</mtext><mo>+</mo><mtext>constant corrections for nozzle size</mtext></mrow><annotation encoding="text/plain">cap R sub effective end-sub is approximately equal to 0.05 center dot cap P sub nozzle end-sub  (in psi) plus constant corrections for nozzle size</annotation></semantics></math> --> Reffective≈0.05⋅Pnozzle (in psi)+constant corrections for nozzle sizecap R sub effective end-sub is approximately equal to 0.05 center dot cap P sub nozzle end-sub  (in psi) plus constant corrections for nozzle size

Smaller nozzle sizes create higher velocity at low flow rates but suffer from **high drag-to-mass ratios**, causing the stream to atomize and drop short. Larger nozzle sizes preserve stream integrity longer but require massive, heavy pumps and high flow rates (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>Q</mi><annotation encoding="text/plain">cap Q</annotation></semantics></math> --> Qcap Q

), increasing the payload weight on the drone. 

---

Calculation Summary 

To find the definitive trajectory, map your variables in this sequence: 

1. Define drone altitude (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>h</mi><annotation encoding="text/plain">h</annotation></semantics></math> --> hh

) and desired flow rate (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>Q</mi><annotation encoding="text/plain">cap Q</annotation></semantics></math> --> Qcap Q

).
2. Select nozzle size (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>d</mi><annotation encoding="text/plain">d</annotation></semantics></math> --> dd

) to balance required exit velocity (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>v</mi><mn>0</mn></msub><annotation encoding="text/plain">v sub 0</annotation></semantics></math> --> v0v sub 0

) against pump weight capacity.
3. Calculate total pressure (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>P</mi><mtext>pump</mtext></msub><annotation encoding="text/plain">cap P sub pump end-sub</annotation></semantics></math> --> Ppumpcap P sub pump end-sub

) ensuring it does not exceed the drone's hose burst pressure.
4. Apply drag-inclusive kinematic equations to resolve final droplet horizontal distance. 

If you have specific numbers, I can run the exact math for you. Please let me know: 

*

* Your target **drone altitude** or **hose length**

* The **flow rate** or **pump pressure capacity** you are using

* Your desired **nozzle diameter** or **target distance** 

*

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

[1] (PDF) Modeling and Simulation of High Pressure Water Mist Systems. Opens in new tab.  
https://www.researchgate.net/publication/257563026_Modeling_and_Simulation_of_High_Pressure_Water_Mist_Systems

[2] Liquid Velocity Calculator. Opens in new tab.  
https://nozzle-pro.com/pages/liquid-velocity-calculator?srsltid=AfmBOooLUNL65X2Sf2nQqZlRRKXRFbnHrHDNAc7mc32aWjjZQsKjCy7M

[3] Untitled. Opens in new tab.  
https://bpb-us-w2.wpmucdn.com/blogs.socsd.org/dist/7/112/files/2024/01/continuity-and-bernouli-packet-and-solns-e689df9ca37344c6.pdf

[4] (PDF) Modeling and Simulation of High Pressure Water Mist Systems. Opens in new tab.  
https://www.researchgate.net/publication/257563026_Modeling_and_Simulation_of_High_Pressure_Water_Mist_Systems

[5] Liquid Velocity Calculator. Opens in new tab.  
https://nozzle-pro.com/pages/liquid-velocity-calculator?srsltid=AfmBOooLUNL65X2Sf2nQqZlRRKXRFbnHrHDNAc7mc32aWjjZQsKjCy7M

[6] Untitled. Opens in new tab.  
https://bpb-us-w2.wpmucdn.com/blogs.socsd.org/dist/7/112/files/2024/01/continuity-and-bernouli-packet-and-solns-e689df9ca37344c6.pdf

[7] (PDF) Modeling and Simulation of High Pressure Water Mist Systems. Opens in new tab.  
https://www.researchgate.net/publication/257563026_Modeling_and_Simulation_of_High_Pressure_Water_Mist_Systems

[8] Liquid Velocity Calculator. Opens in new tab.  
https://nozzle-pro.com/pages/liquid-velocity-calculator?srsltid=AfmBOooLUNL65X2Sf2nQqZlRRKXRFbnHrHDNAc7mc32aWjjZQsKjCy7M

[9] Untitled. Opens in new tab.  
https://bpb-us-w2.wpmucdn.com/blogs.socsd.org/dist/7/112/files/2024/01/continuity-and-bernouli-packet-and-solns-e689df9ca37344c6.pdf

[10] (PDF) Modeling and Simulation of High Pressure Water Mist Systems. Opens in new tab.  
https://www.researchgate.net/publication/257563026_Modeling_and_Simulation_of_High_Pressure_Water_Mist_Systems

[11] Liquid Velocity Calculator. Opens in new tab.  
https://nozzle-pro.com/pages/liquid-velocity-calculator?srsltid=AfmBOooLUNL65X2Sf2nQqZlRRKXRFbnHrHDNAc7mc32aWjjZQsKjCy7M

[12] Untitled. Opens in new tab.  
https://bpb-us-w2.wpmucdn.com/blogs.socsd.org/dist/7/112/files/2024/01/continuity-and-bernouli-packet-and-solns-e689df9ca37344c6.pdf

[13] (PDF) Modeling and Simulation of High Pressure Water Mist Systems. Opens in new tab.  
https://www.researchgate.net/publication/257563026_Modeling_and_Simulation_of_High_Pressure_Water_Mist_Systems

[14] Liquid Velocity Calculator. Opens in new tab.  
https://nozzle-pro.com/pages/liquid-velocity-calculator?srsltid=AfmBOooLUNL65X2Sf2nQqZlRRKXRFbnHrHDNAc7mc32aWjjZQsKjCy7M

[15] Untitled. Opens in new tab.  
https://bpb-us-w2.wpmucdn.com/blogs.socsd.org/dist/7/112/files/2024/01/continuity-and-bernouli-packet-and-solns-e689df9ca37344c6.pdf

