For drone-based aerial tracking in a crowd, **ByteTrack** combined with a custom **Track Prioritization Algorithm** is the most efficient and reliable solution for 2025/2026 deployments. While **DeepSORT** and **StrongSORT** excel at re-identification using appearance features, they suffer from high computational overhead and frequent occlusion failures caused by the top-down perspective of drone footage. `[22][23][24]`

---

Comparison of Tracking Frameworks 

| Feature `[19][20][21]` | ByteTrack | DeepSORT | StrongSORT |
| --- | --- | --- | --- |
| **Primary Mechanism** | Bounding box intersection (<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>I</mi><mi>o</mi><mi>U</mi></mrow><annotation encoding="text/plain">cap I o cap U</annotation></semantics></math> --> IoUcap I o cap U) | Kalman Filter + Re-ID | Advanced Kalman + Strong Re-ID |
| **Drone Suitability** | **Excellent** (Fast, lightweight) | **Poor** (Viewpoint changes break Re-ID) | **Moderate** (Accurate but too slow) |
| **Low-Score Detection** | Keeps low-score boxes for occlusion | Discards low-score boxes | Discards low-score boxes |
| **Compute Overhead** | Extremely Low | Medium | High |

---

1. Framework Selection Analysis 

* **ByteTrack:** This is the ideal baseline. Aerial views shrink target sizes, causing object detectors to output low confidence scores. ByteTrack matches *all* detection boxes (high and low scores) instead of discarding them. This drastically reduces broken trajectories when a person passes under trees or streetlights. `[16][17][18]`
* **DeepSORT / StrongSORT:** These models rely heavily on Deep Appearance Descriptors (Re-ID). From a drone's top-down perspective, people look highly similar (mostly viewing heads and shoulders), which causes the Re-ID embeddings to confuse targets. StrongSORT also introduces too much latency for real-time drone flight controllers. `[13][14][15]`

---

2. Primary Target Selection Strategies 

Once the tracker assigns unique IDs to everyone in the crowd, the drone must programmatically lock onto the "primary target" using specific triggers: 

* **Geofencing / Point-and-Click:** The operator selects a pixel coordinate
  
  
  
  
  
  
. The system maps this to the nearest active Track ID (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>T</mi><mrow><mi>i</mi><mi>d</mi></mrow></msub><annotation encoding="text/plain">cap T sub i d end-sub</annotation></semantics></math> --> Tidcap T sub i d end-sub

). 
* **Anomaly Detection:** The algorithm flags a target exhibiting high-velocity vectors or erratic motion patterns compared to the average crowd flow velocity vector:
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msub><mover accent="true"><mi>V</mi><mo>⃗</mo></mover><mtext>crowd</mtext></msub><mo>=</mo><mfrac><mn>1</mn><mi>N</mi></mfrac><munderover><mo largeop="true" movablelimits="true">∑</mo><mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow><mi>N</mi></munderover><msub><mover accent="true"><mi>V</mi><mo>⃗</mo></mover><mi>i</mi></msub></mrow><annotation encoding="text/plain">modified cap V with right arrow above sub crowd end-sub equals the fraction with numerator 1 and denominator cap N end-fraction sum from i equals 1 to cap N of modified cap V with right arrow above sub i</annotation></semantics></math> --> V⃗crowd=1N∑i=1NV⃗imodified cap V with right arrow above sub crowd end-sub equals the fraction with numerator 1 and denominator cap N end-fraction sum from i equals 1 to cap N of modified cap V with right arrow above sub i
 
* **Attribute Matching:** A lightweight classification head on top of the detector filters targets by specific visual markers (e.g., "red shirt", "carrying backpack"). 

---

3. Track Prioritization Logic 

During a pursuit, the primary target will inevitably be occluded or closely surrounded. Implement a **Priority Score (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>P</mi><annotation encoding="text/plain">cap P</annotation></semantics></math> --> Pcap P

)** for the active track using this objective function: `[10][11][12]`

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>P</mi><mo>=</mo><msub><mi>w</mi><mn>1</mn></msub><mo>⋅</mo><msub><mi>S</mi><mtext>conf</mtext></msub><mo>+</mo><msub><mi>w</mi><mn>2</mn></msub><mo>⋅</mo><mo>(</mo><mn>1</mn><mo>−</mo><msub><mi>D</mi><mtext>center</mtext></msub><mo>)</mo><mo>+</mo><msub><mi>w</mi><mn>3</mn></msub><mo>⋅</mo><msub><mi>I</mi><mtext>IoU</mtext></msub></mrow><annotation encoding="text/plain">cap P equals w sub 1 center dot cap S sub conf end-sub plus w sub 2 center dot open paren 1 minus cap D sub center end-sub close paren plus w sub 3 center dot cap I sub IoU end-sub</annotation></semantics></math> --> P=w1⋅Sconf+w2⋅(1−Dcenter)+w3⋅IIoUcap P equals w sub 1 center dot cap S sub conf end-sub plus w sub 2 center dot open paren 1 minus cap D sub center end-sub close paren plus w sub 3 center dot cap I sub IoU end-sub

Parameter Definitions 

* **
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>S</mi><mtext>conf</mtext></msub><annotation encoding="text/plain">cap S sub conf end-sub</annotation></semantics></math> --> Sconfcap S sub conf end-sub **: The current detection confidence score.
* **
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>D</mi><mtext>center</mtext></msub><annotation encoding="text/plain">cap D sub center end-sub</annotation></semantics></math> --> Dcentercap D sub center end-sub **: Normalized distance from the target's bounding box center to the camera frame center.
* **
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>I</mi><mtext>IoU</mtext></msub><annotation encoding="text/plain">cap I sub IoU end-sub</annotation></semantics></math> --> IIoUcap I sub IoU end-sub **: Intersection over Union with the target's predicted Kalman filter position from the previous frame.
* ** **: Weights adjusted based on altitude (e.g., higher altitude favors
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>I</mi><mtext>IoU</mtext></msub><annotation encoding="text/plain">cap I sub IoU end-sub</annotation></semantics></math> --> IIoUcap I sub IoU end-sub over
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>S</mi><mtext>conf</mtext></msub><annotation encoding="text/plain">cap S sub conf end-sub</annotation></semantics></math> --> Sconfcap S sub conf end-sub

). `[7][8][9]`

---

4. Mitigation of Drone-Specific Challenges 

Camera Motion Compensation (CMC) 

Drone movement skews standard Kalman filter predictions. You must integrate Global Motion Compensation (GMC) via affine transformations or homography matrix estimation (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>H</mi><annotation encoding="text/plain">cap H</annotation></semantics></math> --> Hcap H

) using background pixel tracking (ORB or SIFT features): `[4][5][6]`

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mrow><mo>[</mo><mtable><mtr><mtd><msup><mi>x</mi><mo>′</mo></msup></mtd></mtr><mtr><mtd><msup><mi>y</mi><mo>′</mo></msup></mtd></mtr><mtr><mtd><mn>1</mn></mtd></mtr></mtable><mo>]</mo></mrow><mo>=</mo><mi>H</mi><mrow><mo>[</mo><mtable><mtr><mtd><mi>x</mi></mtd></mtr><mtr><mtd><mi>y</mi></mtd></mtr><mtr><mtd><mn>1</mn></mtd></mtr></mtable><mo>]</mo></mrow></mrow><annotation encoding="text/plain">the 3 by 1 column matrix; x prime, y prime, 1 end-matrix; equals cap H the 3 by 1 column matrix; x, y, 1 end-matrix;</annotation></semantics></math> --> [x′y′1]=H[xy1]the 3 by 1 column matrix; x prime, y prime, 1 end-matrix; equals cap H the 3 by 1 column matrix; x, y, 1 end-matrix;

Target Re-Identification (Re-ID) Lock 

If the Priority Score drops below a critical threshold (total occlusion), the drone should command the gimbal to hold its last known trajectory vector while executing an expanding spiral search pattern until ByteTrack re-establishes the target ID match. 

---

✅ Summary of Solution 

For an aerial drone tracking a specific person in a crowd, use **ByteTrack** paired with **Global Motion Compensation (GMC)** to maintain steady tracking coordinates. Select the target via **geofencing**, and maintain lock using a **multi-factor Priority Score function** that balances motion prediction (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>I</mi><mi>o</mi><mi>U</mi></mrow><annotation encoding="text/plain">cap I o cap U</annotation></semantics></math> --> IoUcap I o cap U

) with spatial frame centering. 

---

If you want to build out the software architecture, let me know: 

* Your hardware constraints (**Edge AI chip** like Jetson Orin, or **Cloud streaming**?)
* The operational drone altitude (**Low-altitude** tactical or **High-altitude** surveillance?)
* Expected **crowd density** (Sparse walking vs. dense festival environment?) 

I can provide the Python architecture or specific Kalman filter tuning parameters for your use case. `[1][2][3]`

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

[1] How Top AI Multi-Object Trackers Perform in Real-World Scenarios? - Expert Tech Partner for Scalable Software Development. Opens in new tab.  
https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/

[2] Deep Dive into Fundamentals of DeepSORT for Object Tracking. Opens in new tab.  
https://medium.com/@shasvatdesai/deep-dive-into-fundamentals-of-deepsort-for-object-tracking-f92ec7abfa7e

[3] Deep Drone: Object Detection and Tracking for Smart Drones on Embedded System. Opens in new tab.  
https://web.stanford.edu/class/cs231a/prev_projects_2016/deep-drone-object__2_.pdf

[4] How Top AI Multi-Object Trackers Perform in Real-World Scenarios? - Expert Tech Partner for Scalable Software Development. Opens in new tab.  
https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/

[5] Deep Dive into Fundamentals of DeepSORT for Object Tracking. Opens in new tab.  
https://medium.com/@shasvatdesai/deep-dive-into-fundamentals-of-deepsort-for-object-tracking-f92ec7abfa7e

[6] Deep Drone: Object Detection and Tracking for Smart Drones on Embedded System. Opens in new tab.  
https://web.stanford.edu/class/cs231a/prev_projects_2016/deep-drone-object__2_.pdf

[7] How Top AI Multi-Object Trackers Perform in Real-World Scenarios? - Expert Tech Partner for Scalable Software Development. Opens in new tab.  
https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/

[8] Deep Dive into Fundamentals of DeepSORT for Object Tracking. Opens in new tab.  
https://medium.com/@shasvatdesai/deep-dive-into-fundamentals-of-deepsort-for-object-tracking-f92ec7abfa7e

[9] Deep Drone: Object Detection and Tracking for Smart Drones on Embedded System. Opens in new tab.  
https://web.stanford.edu/class/cs231a/prev_projects_2016/deep-drone-object__2_.pdf

[10] How Top AI Multi-Object Trackers Perform in Real-World Scenarios? - Expert Tech Partner for Scalable Software Development. Opens in new tab.  
https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/

[11] Deep Dive into Fundamentals of DeepSORT for Object Tracking. Opens in new tab.  
https://medium.com/@shasvatdesai/deep-dive-into-fundamentals-of-deepsort-for-object-tracking-f92ec7abfa7e

[12] Deep Drone: Object Detection and Tracking for Smart Drones on Embedded System. Opens in new tab.  
https://web.stanford.edu/class/cs231a/prev_projects_2016/deep-drone-object__2_.pdf

[13] How Top AI Multi-Object Trackers Perform in Real-World Scenarios? - Expert Tech Partner for Scalable Software Development. Opens in new tab.  
https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/

[14] Deep Dive into Fundamentals of DeepSORT for Object Tracking. Opens in new tab.  
https://medium.com/@shasvatdesai/deep-dive-into-fundamentals-of-deepsort-for-object-tracking-f92ec7abfa7e

[15] Deep Drone: Object Detection and Tracking for Smart Drones on Embedded System. Opens in new tab.  
https://web.stanford.edu/class/cs231a/prev_projects_2016/deep-drone-object__2_.pdf

[16] How Top AI Multi-Object Trackers Perform in Real-World Scenarios? - Expert Tech Partner for Scalable Software Development. Opens in new tab.  
https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/

[17] Deep Dive into Fundamentals of DeepSORT for Object Tracking. Opens in new tab.  
https://medium.com/@shasvatdesai/deep-dive-into-fundamentals-of-deepsort-for-object-tracking-f92ec7abfa7e

[18] Deep Drone: Object Detection and Tracking for Smart Drones on Embedded System. Opens in new tab.  
https://web.stanford.edu/class/cs231a/prev_projects_2016/deep-drone-object__2_.pdf

[19] How Top AI Multi-Object Trackers Perform in Real-World Scenarios? - Expert Tech Partner for Scalable Software Development. Opens in new tab.  
https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/

[20] Deep Dive into Fundamentals of DeepSORT for Object Tracking. Opens in new tab.  
https://medium.com/@shasvatdesai/deep-dive-into-fundamentals-of-deepsort-for-object-tracking-f92ec7abfa7e

[21] Deep Drone: Object Detection and Tracking for Smart Drones on Embedded System. Opens in new tab.  
https://web.stanford.edu/class/cs231a/prev_projects_2016/deep-drone-object__2_.pdf

[22] How Top AI Multi-Object Trackers Perform in Real-World Scenarios? - Expert Tech Partner for Scalable Software Development. Opens in new tab.  
https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/

[23] Deep Dive into Fundamentals of DeepSORT for Object Tracking. Opens in new tab.  
https://medium.com/@shasvatdesai/deep-dive-into-fundamentals-of-deepsort-for-object-tracking-f92ec7abfa7e

[24] Deep Drone: Object Detection and Tracking for Smart Drones on Embedded System. Opens in new tab.  
https://web.stanford.edu/class/cs231a/prev_projects_2016/deep-drone-object__2_.pdf

