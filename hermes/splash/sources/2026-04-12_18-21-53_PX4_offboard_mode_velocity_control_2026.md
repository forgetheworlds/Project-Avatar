In 2026, **PX4 Offboard Mode** continues to be the standard for high-level autonomous drone control, requiring a continuous heartbeat of at least **2 Hz** to remain active. For smooth cinematic filming, developers prioritize **velocity setpoints** over position setpoints to avoid the "rocky," jerky motion typical of hard acceleration and stops. 

MAVSDK Velocity Control for Filming `[1][2][3]`

For fluid cinematic movement, the [MAVSDK Offboard plugin](https://mavsdk.mavlink.io/main/en/cpp/guide/offboard.html) is used to send direct velocity commands. 

* **Coordinate Frames**:
  + **NED (North, East, Down)**: Best for global trajectory tracking (e.g., following a specific path on a map).
  + **Body Frame (Forward, Right, Down)**: Ideal for "follow-me" or relative filming where the drone moves relative to its own heading.
* **Smoothing Technique**: Instead of jumping directly to a target velocity, implement a **ramp-up/down** in your companion computer's script. Gradually incrementing the velocity setpoints (e.g., at 20 Hz) ensures the drone's internal PID controllers produce smooth, non-aggressive transitions.
* **Yaw Control**: To keep a subject in frame while moving, use `set_velocity_body` or `set_velocity_ned` with a defined **yaw rate** or **yaw heading**. 

Key Flight & Setup Parameters 

Smoothness starts with a properly tuned vehicle. In 2026, PX4 allows for fine-tuning the **Vertical Velocity Controller** to avoid aggressive vertical "bouncing". 

* **MPC_Z_VEL_MAX_UP / DOWN**: Limit these (e.g., 3 m/s up, 1.5 m/s down) to prevent aggressive vertical shifts during filming.
* **MPC_XY_VEL_P**: Ensure the proportional gain is high enough for crisp response but low enough to avoid the "Parkinson's-like" shaking seen in poorly tuned offboard velocity setups.
* **Hardware for Filming**: For custom filming rigs, the Pixhawk 2.4.8 remains a cost-effective choice for developers using MAVSDK and companion computers. 

Advanced Trajectory Tracking 

For complex shots, combining **position and velocity** in a single message allows the position controller to use the velocity as a **feed-forward value**, significantly improving tracking accuracy along a path. 

* **Setpoints**: Use `set_position_velocity_ned` to provide a target coordinate while simultaneously defining the intended speed toward that target.
* **Failsafes**: Always maintain a manual override. Toggling the flight mode switch to **Position** or **Altitude** mode will immediately kill offboard control if a programmatic error occurs. 

Would you like a **Python code snippet** demonstrating how to implement a **velocity ramp** for smoother cinematic starts? 

Copy

Creating a public link...

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

A copy of this chat will be included with your feedback

A copy of this chat and your uploaded image will be included with your feedback

Your feedback will include a copy of this chat, any links you shared, and the image from your search.

Thanks for letting us know

Google may use account and system data to understand your feedback and improve our services, subject to our [Privacy Policy](https://policies.google.com/privacy) and [Terms of Service](https://policies.google.com/terms). For legal issues, [make a legal removal request](https://support.google.com/legal/answer/3110420).

---

## Sources:

[1] Velocity and Position Control in Offboard Mode - PX4 Autopilot. Opens in new tab.  
https://discuss.px4.io/t/velocity-and-position-control-in-offboard-mode/37107#:~:text=Hi%20@gabedavid%20%2C%20there%20is%20no,your%20attitude%20setpoints%20keep%20changing.

[2] (PX4-MAVSDK) Trying to navigate by velocity using PID in .... Opens in new tab.  
https://www.reddit.com/r/drones/comments/1mgxgdf/px4mavsdk_trying_to_navigate_by_velocity_using/

[3] Offboard Mode (Generic/All Frames) | PX4 Guide (main). Opens in new tab.  
https://docs.px4.io/main/en/flight_modes/offboard#:~:text=Manual%20control%20is%20disabled%20except,to%20offboard%20mode%20when%20flying.

