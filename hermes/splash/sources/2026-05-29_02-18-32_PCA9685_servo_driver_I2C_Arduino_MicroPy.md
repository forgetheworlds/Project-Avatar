The **PCA9685** is an

-controlled, **16-channel, 12-bit PWM controller** that offloads heavy timing requirements from host microcontrollers like the ESP32, Arduino, or Raspberry Pi Pico running MicroPython. In **2025/2026 drone pan-tilt systems**, minimizing weight and maximizing flight time makes the choice between utilizing direct GPIO control and an external PCA9685 driver critical. `[40][41][42]`

---

⚖️ Weight Comparison: Direct GPIO vs. PCA9685 (ESP32 Drone) 

For a standard drone pan-tilt system, **Direct ESP32 GPIO control is lighter** for small setups (up to 4 servos), while the **PCA9685 saves weight** in massive setups (5+ servos) by consolidating heavy copper power routing. `[37][38][39]`

| Metric / Component `[34][35][36]` | Direct ESP32 GPIO Control | PCA9685 Breakout Board Setup |
| --- | --- | --- |
| **Hardware Weight** | **<br>** (Uses existing microcontroller pins) | **<br> to<br><br>** (PCB, chip, and header pins) |
| **Wiring Mass** | High per servo (Individual<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>+</mo><annotation encoding="text/plain">positive</annotation></semantics></math> --> +positive,<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>−</mo><annotation encoding="text/plain">negative</annotation></semantics></math> --> −negative, Signal lines to FC) | Low (Single<br><br> bus<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>+</mo><annotation encoding="text/plain">positive</annotation></semantics></math> --> +positive heavy gauge local power hub) |
| **Max Servos** | Limited by free GPIOs (<br><br><br> max) | Up to **16 servos** per board (64 boards chainable) |
| **Payload Verdict** | **Best for ultra-light drones (1–4 servos)** | **Best for heavy-payload / hexapods (5+ servos)** |

---

1. Configure PWM Frequency 

Servos require a specific refresh cycle to maintain positioning torque without overheating. Standard analog servos operate at

( period). Modern digital pan-tilt servos can leverage up to for instantaneous response corrections during flight maneuvers. `[31][32][33]`

The PCA9685 handles frequencies from ** to ** using an internal oscillator.

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mtext>Prescale Value</mtext><mo>=</mo><mtext>round</mtext><mrow><mo>(</mo><mfrac><mn>25000000</mn><mrow><mn>4096</mn><mo>×</mo><mtext>Frequency</mtext></mrow></mfrac><mo>)</mo></mrow><mo>−</mo><mn>1</mn></mrow><annotation encoding="text/plain">Prescale Value equals round open paren the fraction with numerator 25000000 and denominator 4096 cross Frequency end-fraction close paren minus 1</annotation></semantics></math> --> Prescale Value=round(250000004096×Frequency)−1Prescale Value equals round open paren the fraction with numerator 25000000 and denominator 4096 cross Frequency end-fraction close paren minus 1

---

2. Map 12-Bit Resolution 

The PCA9685 features a **12-bit resolution**, meaning each PWM cycle is divided into exactly **4096 discrete steps** (from

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mn>0</mn><annotation encoding="text/plain">0</annotation></semantics></math> --> 00 to

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mn>4095</mn><annotation encoding="text/plain">4095</annotation></semantics></math> --> 40954095

). `[28][29][30]`

At a standard drone servo frequency of

( total window), each step represents exactly:

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mfrac><mrow><mn>20000</mn><mtext> </mtext><mi>μ</mi><mtext>s</mtext></mrow><mn>4096</mn></mfrac><mo>≈</mo><mn>4.88</mn><mtext> </mtext><mi>μ</mi><mtext>s per step</mtext></mrow><annotation encoding="text/plain">the fraction with numerator 20000 space mu s and denominator 4096 end-fraction is approximately equal to 4.88 space mu s per step</annotation></semantics></math> --> 20000 μs4096≈4.88 μs per stepthe fraction with numerator 20000 space mu s and denominator 4096 end-fraction is approximately equal to 4.88 space mu s per step

Standard servo pulses range from

(

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mn>0</mn><mo>∘</mo></msup><annotation encoding="text/plain">0 raised to the composed with power</annotation></semantics></math> --> 0∘0 raised to the composed with power

) to

(

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msup><mn>180</mn><mo>∘</mo></msup><annotation encoding="text/plain">180 raised to the composed with power</annotation></semantics></math> --> 180∘180 raised to the composed with power

). To map this in your code: `[25][26][27]`

* **

  
  
  
(Minimum pulse):**  counts.
* **

  
  
  
(Neutral center):**  counts.
* **

  
  
  
(Maximum pulse):**  counts. 

---

3. Eliminate Jitter 

Jitter degrades camera stabilization on drone gimbals. 

* **Direct GPIO Jitter:** High if the OS or processor shares threads (e.g., handling Wi-Fi/Bluetooth stacks on an ESP32). Interrupt latencies can cause micro-stutters in the servo arm. `[22][23][24]`
* **PCA9685 Jitter:** Practically **zero**. Because it communicates via updates, the chip continuously drives the hardware PWM completely independently of what the ESP32 processing cores are doing. `[19][20][21]`

---

4. Isolate Power Wiring  **Never power servos directly from your microcontroller's or rail.** Drone servos pull high surge currents (up to per servo under aerodynamic load/stalls), which will brown out your flight controller and cause a crash. `[16][17][18]`

1. **Logic Power (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>V</mi><mrow><mi>C</mi><mi>C</mi></mrow></msub><annotation encoding="text/plain">cap V sub cap C cap C end-sub</annotation></semantics></math> --> VCCcap V sub cap C cap C end-sub

):** Connect the ESP32 output directly to the PCA9685
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>V</mi><mrow><mi>C</mi><mi>C</mi></mrow></msub><annotation encoding="text/plain">cap V sub cap C cap C end-sub</annotation></semantics></math> --> VCCcap V sub cap C cap C end-sub pin for safe logic lines ( logic levels). 
2. **Servo Power (
  
  
Terminal):** Connect a dedicated to external Battery Elimination Circuit (BEC) or voltage regulator directly to the blue/green screw terminal block on the PCA9685. `[13][14][15]`
3. **Grounding (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>G</mi><mi>N</mi><mi>D</mi></mrow><annotation encoding="text/plain">cap G cap N cap D</annotation></semantics></math> --> GNDcap G cap N cap D

):** Ensure all grounds (
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>G</mi><mi>N</mi><mi>D</mi></mrow><annotation encoding="text/plain">cap G cap N cap D</annotation></semantics></math> --> GNDcap G cap N cap D of the ESP32,
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>G</mi><mi>N</mi><mi>D</mi></mrow><annotation encoding="text/plain">cap G cap N cap D</annotation></semantics></math> --> GNDcap G cap N cap D of the external BEC, and
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>G</mi><mi>N</mi><mi>D</mi></mrow><annotation encoding="text/plain">cap G cap N cap D</annotation></semantics></math> --> GNDcap G cap N cap D of the PCA9685) are tied together to create a common reference point. `[10][11][12]`

---

5. Control Multiple Servos `[7][8][9]`

The PCA9685 enables consecutive or staggered updates to multiple servos via single-byte address shifts over

. `[4][5][6]`

Arduino C++ Configuration (Using Adafruit PWM Servo Driver Library) `[1][2][3]` cpp

```
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// Initialized with default I2C address 0x40
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

#define SERVO_FREQ 50 // 50Hz update rate for analog drone servos void setup() { pwm.begin();
  pwm.setOscillatorFrequency(27000000); // Calibrate to specific board variations pwm.setPWMFreq(SERVO_FREQ);
} void loop() {
  // Move Pan Servo on Channel 0 to 0 degrees (205 counts) pwm.setPWM(0, 0, 205);
  // Move Tilt Servo on Channel 1 to 180 degrees (410 counts) pwm.setPWM(1, 0, 410);
  delay(1000);
}

```

Use code with caution.

MicroPython Configuration (ESP32 / Pi Pico)  python

``` from machine import I2C, Pin import time class PCA9685:
    def __init__(self, i2c, address=0x40):
        self.i2c = i2c self.address = address self.reset() def reset(self):
        self.i2c.writeto_mem(self.address, 0x00, b'\x00') # Mode 1 Reset def set_freq(self, freq):
        prescale = int(25000000 / (4096 * freq) + 0.5) - 1 self.i2c.writeto_mem(self.address, 0x00, b'\x10') # Sleep Mode to set prescale self.i2c.writeto_mem(self.address, 0xFE, bytes([prescale])) self.i2c.writeto_mem(self.address, 0x00, b'\xA0') # Restart Mode 1 with Auto-Increment time.sleep_ms(5) def set_pwm(self, channel, on, off):
        base_reg = 0x06 + (4 * channel)
        # Writes ON time bytes and OFF time bytes to the 4 registers per channel data = bytes([on & 0xFF, (on >> 8) & 0xFF, off & 0xFF, (off >> 8) & 0xFF]) self.i2c.writeto_mem(self.address, base_reg, data)

# Hardware Initialization i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000) driver = PCA9685(i2c) driver.set_freq(50)

# Set Channel 0 (Pan) to 1500us Neutral position (307 counts) driver.set_pwm(0, 0, 307)

```

Use code with caution.

---

✅ Summary of Weights and Configurations 

For an ultra-lightweight drone pan-tilt system, use direct GPIO pins if you have only two servos. If you require zero-jitter camera tracking, or are driving multiple peripheral mechanisms alongside your gimbal, add the PCA9685 chip. 

To optimize your drone build further, let me know: 

* The **exact number and model** of the pan-tilt servos you plan to use.
* Your target **payload weight budget** or drone class size.
* Whether your firmware requires **real-time camera tracking** input (like OpenCV or an onboard AI module). 

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

[1] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[2] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[3] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[4] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[5] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[6] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[7] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[8] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[9] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[10] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[11] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[12] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[13] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[14] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[15] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[16] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[17] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[18] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[19] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[20] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[21] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[22] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[23] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[24] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[25] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[26] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[27] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[28] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[29] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[30] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[31] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[32] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[33] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[34] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[35] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[36] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[37] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[38] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[39] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

[40] 2pcs PCA9685 16 Channel 12 bit PWM Servo Motor Driver IIC Interface Compatible with Arduino Raspberry Pi. Opens in new tab.  
https://www.amazon.ca/PCA9685-Channel-Interface-Compatible-Raspberry/dp/B0BVVT644H

[41] PCA9685 16 Channel 12 Bit PWM Servo Driver Board Module Controller for Arduino And Raspberry Pi COM44, R15. Opens in new tab.  
https://www.faranux.com/product/21366/

[42] Servo Driver HAT. Opens in new tab.  
https://www.waveshare.com/wiki/Servo_Driver_HAT?srsltid=AfmBOoo_PVDLh5z6dQD3sFKprxUYpC_D4Gf-ltwgMe-DkQqWVNOxU_b1

