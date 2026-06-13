To build a high-performance pan-tilt camera auto-aim tracking loop using **SG90** or **MG90S** servos, you must minimize latency across your computer vision (CV) pipeline and implement a robust control algorithm. 

The optimal control output is achieved using a **Parallel PID Controller with Velocity Feedforward and Conditional Integration Anti-Windup**. 

---

1. The Mathematical Control Law 

The complete mathematical formula for calculating the control output at any given timestamp is: 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>u</mi><mo>(</mo><mi>t</mi><mo>)</mo><mo>=</mo><msub><mi>K</mi><mi>p</mi></msub><mi>e</mi><mo>(</mo><mi>t</mi><mo>)</mo><mo>+</mo><msub><mi>K</mi><mi>i</mi></msub><msubsup><mo largeop="true">∫</mo><mn>0</mn><mi>t</mi></msubsup><mi>e</mi><mo>(</mo><mi>τ</mi><mo>)</mo><mi>d</mi><mi>τ</mi><mo>+</mo><msub><mi>K</mi><mi>d</mi></msub><mfrac><mrow><mi>d</mi><mi>e</mi><mo>(</mo><mi>t</mi><mo>)</mo></mrow><mrow><mi>d</mi><mi>t</mi></mrow></mfrac><mo>+</mo><msub><mi>K</mi><mrow><mi>f</mi><mi>f</mi></mrow></msub><msub><mi>v</mi><mrow><mi>t</mi><mi>a</mi><mi>r</mi><mi>g</mi><mi>e</mi><mi>t</mi></mrow></msub><mo>(</mo><mi>t</mi><mo>)</mo></mrow><annotation encoding="text/plain">u open paren t close paren equals cap K sub p e open paren t close paren plus cap K sub i integral from 0 to t of e open paren tau close paren d tau plus cap K sub d the fraction with numerator d e open paren t close paren and denominator d t end-fraction plus cap K sub f f end-sub v sub t a r g e t end-sub open paren t close paren</annotation></semantics></math> --> u(t)=Kpe(t)+Ki∫0te(τ)dτ+Kdde(t)dt+Kffvtarget(t)u open paren t close paren equals cap K sub p e open paren t close paren plus cap K sub i integral from 0 to t of e open paren tau close paren d tau plus cap K sub d the fraction with numerator d e open paren t close paren and denominator d t end-fraction plus cap K sub f f end-sub v sub t a r g e t end-sub open paren t close paren

Where: 

* 

  
  
  
: Target pixel error (Target Position - Current Position)
* 

  
  
  
: Target velocity calculated from the CV bounding box frame-to-frame movement 

---

2. Implementation Script (Python) 

This complete Python class implements the full control law, featuring an anti-windup clamp and a low-pass filter on the derivative term to suppress high-frequency sensor noise.  python

``` import time class PanTiltPID:
    def __init__(self, kp, ki, kd, kff, min_output=0, max_output=180, alpha=0.3):
        # Controller Gains self.kp = kp self.ki = ki self.kd = kd self.kff = kff
  
        # Actuator Constraints (SG90/MG90S Degree Limits) self.min_output = min_output self.max_output = max_output
  
        # Low-pass filter coefficient for derivative noise suppression (0 < alpha <= 1) self.alpha = alpha
  
        # State Variables self.integral = 0.0 self.last_error = 0.0 self.last_time = None self.filtered_derivative = 0.0 def update(self, error, target_velocity=0.0):
        current_time = time.perf_counter() if self.last_time is None:
            self.last_time = current_time self.last_error = error return self.min_output + (self.max_output - self.min_output) / 2.0 dt = current_time - self.last_time if dt <= 0.0:
            dt = 1e-5  # Prevent division by zero
  
        # Proportional Term p_term = self.kp * error
  
        # Derivative Term with Low-Pass Filtering raw_derivative = (error - self.last_error) / dt self.filtered_derivative = (self.alpha * raw_derivative) + ((1.0 - self.alpha) * self.filtered_derivative) d_term = self.kd * self.filtered_derivative
  
        # Feedforward Term (Predictive action based on target speed) ff_term = self.kff * target_velocity
  
        # Preliminary Output calculation (excluding Integration) pre_output = p_term + d_term + ff_term
  
        # Conditional Integration (Anti-Windup Clamping)
        # Only integrate if the actuator is not saturated, or if integrating drives it out of saturation potential_integral = self.integral + (error * dt) potential_output = pre_output + (self.ki * potential_integral) if self.min_output <= potential_output <= self.max_output:
            self.integral = potential_integral i_term = self.ki * self.integral
  
        # Final Total Output Assembly output = p_term + i_term + d_term + ff_term
  
        # Hard Actuator Clamp output = max(self.min_output, min(output, self.max_output))
  
        # State Update self.last_error = error self.last_time = current_time return output

```

Use code with caution.

---

3. Tuning Strategy & Response Curves 

[SG90 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:1008667087336457496,gpcid:15958465142671551659,headlineOfferDocid:1983664571738359372,catalogid:16488157821851188968,productDocid:16984186196846455204&q=product&sa=X&ved=2ahUKEwj7l-TP5d2UAxUEg4kEHWigMEkQxa4PeggIAggACBIQAg)

(plastic gears) and

[MG90S Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462440460801242,imageDocid:3995136972998272822,gpcid:6967018807386753364,headlineOfferDocid:15179067079765691560,catalogid:17521970663455173741,productDocid:5003044497117870641,rds:PC_6967018807386753364%7CPROD_PC_6967018807386753364&q=product&sa=X&ved=2ahUKEwj7l-TP5d2UAxUEg4kEHWigMEkQxa4PeggIAggACBIQBA)

(metal gears) possess severe physical deadbands, gear backlash, and low torque profiles. Standard Ziegler-Nichols tuning methods fail here due to continuous oscillations caused by gear slop. Use a manual heuristics-based tuning sequence instead: `[4][5][6]`

```
Response Types:
Output Position
  ^

  |        /---\     /---\           <- Aggressive Over-tuned (High Kp / Low Kd)
  |       /     \   /     \
  |      /       ---       \--- Target

  |    /-----------------------      <- Optimally Critically Damped (Balanced PID)
  |  /
  | /                                <- Under-tuned Sluggish (Low Kp)
  +-------------------------------------> Time

```

Step-by-Step Manual Tuning Protocol 

1. **Zero Out Gains**: Set
  
  
,
  
  
,
  
  
,

2. **Find Proportional Floor**: Increase
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>p</mi></msub><annotation encoding="text/plain">cap K sub p</annotation></semantics></math> --> Kpcap K sub p slowly until the camera tracks an moving object but exhibits a lagging, lazy response curve (under-damped). If the gimbal begins rapidly shaking in place, immediately scale
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>p</mi></msub><annotation encoding="text/plain">cap K sub p</annotation></semantics></math> --> Kpcap K sub p down by 40%. 
3. **Inject Dampening**: Increase
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>d</mi></msub><annotation encoding="text/plain">cap K sub d</annotation></semantics></math> --> Kdcap K sub d to eliminate overshoot and halt oscillations. 
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>d</mi></msub><annotation encoding="text/plain">cap K sub d</annotation></semantics></math> --> Kdcap K sub d counteracts the aggressive momentum of
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>p</mi></msub><annotation encoding="text/plain">cap K sub p</annotation></semantics></math> --> Kpcap K sub p

. Stop increasing if the camera motion feels "jittery" or overly sensitive to pixel variations. 
4. **Eliminate Steady-State Droop**: If your drone or target stops moving and the camera remains fixed a few pixels away from the absolute center, increase
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>i</mi></msub><annotation encoding="text/plain">cap K sub i</annotation></semantics></math> --> Kicap K sub i in tiny increments to force the tracking error to absolute zero. 
5. **Feedforward Match**: Introduce
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mrow><mi>f</mi><mi>f</mi></mrow></msub><annotation encoding="text/plain">cap K sub f f end-sub</annotation></semantics></math> --> Kffcap K sub f f end-sub only if tracking high-speed targets. Match
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mrow><mi>f</mi><mi>f</mi></mrow></msub><annotation encoding="text/plain">cap K sub f f end-sub</annotation></semantics></math> --> Kffcap K sub f f end-sub to your camera's field of view so that if an object moves across the frame at
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>X</mi><annotation encoding="text/plain">cap X</annotation></semantics></math> --> Xcap X pixels/second, the feedforward output immediately steps the servo to match that angle natively without waiting for an error metric to accumulate. 

---

4. Latency Optimization for CV Control Loops 

A classic mistake is executing Inference, Tracking, and Servo Write sequentially on a single thread. This stacks delays (

) causing severe controller phase lag and immediate control loop destabilization. 

Architecture Checklist 

* **Decouple Threads**: Dedicate one high-priority execution thread solely to updating the `PanTiltPID` math and outputting PWM pulses to the hardware at a fixed rate (e.g.,
  
  
). Execute Object Detection (e.g., YOLO / MobileNet) asynchronously on a separate worker thread. 
* **Frame Drop Strategy**: Never queue incoming camera frames. If the CV thread is busy processing a frame, immediately drop any newly arriving frames. Always read the absolute freshest frame off your camera buffer (`O_NONBLOCK` or clearing the buffer memory stack). 

* **Hardware Selection Bottlenecks**:
  + **[MacBook Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462781479953300,imageDocid:5315571854492594069,gpcid:16366108998644221033,headlineOfferDocid:3446622368329379513,catalogid:11555311375605611356,productDocid:13340089820873184309,rds:PC_16366108998644221033%7CPROD_PC_16366108998644221033&q=product&sa=X&ved=2ahUKEwj7l-TP5d2UAxUEg4kEHWigMEkQxa4PeggIAggACBsQCg)

(M1/M2/M3/M4 Architecture)**: Leverage Apple Silicon hardware acceleration by exporting models to CoreML or utilizing the `MPS` (Metal Performance Shaders) backend in PyTorch. Ensure frames are captured natively via AVFoundation via an optimized OpenCV build.
  + **Raspberry Pi 4 / 5**: Do not run native FP32 desktop tracking models on the CPU. Convert models to INT8 quantization matrices and run them via an external edge accelerator like a **Coral Edge TPU**, or optimize strictly for the **RPi 5 OpenGLES / Hailo-8L** hardware suites. 

---

5. Hardware Actuator Specifics 

| Hardware Trait `[1][2][3]` | SG90 Servo | MG90S Servo |
| --- | --- | --- |
| **Gear Material** | Plastic | Metal |
| **Backlash / Slop** | High (<br><br>) | Moderate (<br><br>) |
| **Deadband Window** | <br><br><br> | <br><br><br> |
| **Control Action** | Use higher LPF filtering (`alpha = 0.2`) | Responsive; allows larger<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>K</mi><mi>d</mi></msub><annotation encoding="text/plain">cap K sub d</annotation></semantics></math> --> Kdcap K sub d values |
> **Power Notice**: Never power SG90 or MG90S servos directly from a Raspberry Pi's
>
> 
>
> 
>
> rail. The inductive current spikes during sudden directional changes will brown out the Pi's CPU. Always use an external
>
> 
>
> 
>
>
>
> 
>
> 
>
> BEC/Buck Converter shared to a common ground with your control computer.

---

✅ Summary of Tuning & Optimization Architecture 

The core requirement of this architecture is separating the computer vision model's processing latency from the fast physical requirements of the servo motor's stabilization control loop. By wrapping a robust anti-windup clamping threshold around the parallel PID calculations, your drone gimbal can dynamically track fast targets without spinning out into uncontrollable self-reinforcing oscillations. 

If you would like to proceed with configuring this system, let me know: 

* Which **single-board computer or machine model** you are deploying this code on.
* The specific **Object Detection model family** you plan to implement.
* Your current **hardware capture frame rate (FPS)** target. 

I can write a fully multithreaded framework separating the CV ingestion loop from your hardware-timed servo outputs. 

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

[1] Prime Robotics Servo Bracket PT Pan/Tilt Camera Mount + 2 Pieces of Servo Motor SG90. Opens in new tab.  
https://www.amazon.in/Prime-Robotics-Bracket-Camera-Pieces/dp/B084LR836N

[2] MG90S Metal Gear Servo Motor – 180° Positional Rotation. Opens in new tab.  
https://www.voltaat.com/products/mg90s-metal-gear-servo-positional-rotation

[3] SG90 Mini Micro Servo for RC 250 450 Helicopter Car Liberia | Ubuy. Opens in new tab.  
https://www.liberia.ubuy.com/product/59KA7VFJU-sg90-mini-micro-servo-for-rc-250-450-helicopter-car-foamy-plane-robot-arm-helicopter-airplane-remote-controller-motor-9g-1-6kg

[4] Prime Robotics Servo Bracket PT Pan/Tilt Camera Mount + 2 Pieces of Servo Motor SG90. Opens in new tab.  
https://www.amazon.in/Prime-Robotics-Bracket-Camera-Pieces/dp/B084LR836N

[5] MG90S Metal Gear Servo Motor – 180° Positional Rotation. Opens in new tab.  
https://www.voltaat.com/products/mg90s-metal-gear-servo-positional-rotation

[6] SG90 Mini Micro Servo for RC 250 450 Helicopter Car Liberia | Ubuy. Opens in new tab.  
https://www.liberia.ubuy.com/product/59KA7VFJU-sg90-mini-micro-servo-for-rc-250-450-helicopter-car-foamy-plane-robot-arm-helicopter-airplane-remote-controller-motor-9g-1-6kg

