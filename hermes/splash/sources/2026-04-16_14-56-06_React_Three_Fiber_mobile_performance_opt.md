In React Three Fiber (R3F), optimizing the **Device Pixel Ratio (DPR)** is one of the most effective ways to boost mobile performance. High-density mobile screens (like Retina displays) often have a DPR of 3 or higher, meaning the GPU has to process up to nine times more pixels than a standard display. 

1. Cap the DPR `[13][14][15][16][17][18]`

The standard recommendation for mobile is to **cap the DPR at 1.5 or 2**. This drastically reduces the GPU fill-rate pressure with almost no visible loss in quality on small screens. 

You can set this directly on the `<Canvas>` component using an array to define a minimum and maximum range: `[7][8][9][10][11][12]` jsx

```
<Canvas dpr={[1, 1.5]}>
  {/* Your scene */}
</Canvas>

```

Use code with caution.

Copied to clipboard

*Note: R3F defaults to `clamp(window.devicePixelRatio, 1, 2)` if you don't specify it*. 

2. Adaptive/Dynamic DPR Scaling 

For more demanding scenes, you can dynamically lower the resolution based on real-time performance using the [PerformanceMonitor](https://r3f.docs.pmnd.rs/advanced/scaling-performance) from the `@react-three/drei` library. 

* **How it works:** It monitors the framerate and provides a `factor` (0 to 1) that you can use to scale the DPR down when performance drops.
* **Implementation:** jsx
  

``` import { PerformanceMonitor } from '@react-three/drei' import { useState } from 'react' function App() { const [dpr, setDpr] = useState(1.5) return (
    <Canvas dpr={dpr}>
      <PerformanceMonitor onChange={({ factor }) => setDpr(0.5 + factor)} />
      {/* ... */}
    </Canvas>
  )
}
```
  Use code with caution.

Copied to clipboard

 

3. Key Mobile Performance Gains 

* **Disable Antialiasing at Low DPR:** If your DPR drops below 1.2, consider disabling `antialias` to save further resources, as the lower resolution makes aliasing less noticeable anyway.
* **Lower Target FPS for Scaling:** If using adaptive scaling, set your target threshold slightly lower (e.g., 45-50 FPS) to prevent constant "flip-flopping" between resolutions.
* **Battery Efficiency:** High DPR consumes significantly more battery. Capping it even if the frame rate is stable is better for mobile user experience. 

Summary of Best Practices 

| Strategy `[1][2][3][4][5][6]` | Implementation | Benefit |
| --- | --- | --- |
| **Static Cap** | `dpr={[1, 1.5]}` | Prevents over-rendering on high-DPI phones. |
| **Dynamic Scaling** | `PerformanceMonitor` | Lowers resolution only during intense heavy-duty tasks. |
| **Manual Override** | `Math.min(devicePixelRatio, 1.5)` | Simple, one-time calculation for all devices. |

If you'd like, I can provide a more **detailed performance checklist** or show you how to **integrate the PerformanceMonitor** with specific post-processing effects. 

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

Your feedback will include a copy of this chat and the image from your search

Your feedback will include a copy of this chat, any links you shared, and the image from your search.

Thanks for letting us know

Google may use account and system data to understand your feedback and improve our services, subject to our [Privacy Policy](https://policies.google.com/privacy) and [Terms of Service](https://policies.google.com/terms). For legal issues, [make a legal removal request](https://support.google.com/legal/answer/3110420).

---

## Sources:

[1] Scaling performance - React Three Fiber. Opens in new tab.  
https://r3f.docs.pmnd.rs/advanced/scaling-performance#:~:text=It%20gives%20you%20a%20factor,performance%20changes%20on%20their%20own.

[2] Looking for Performance Improvement Consultation : r/threejs. Opens in new tab.  
https://www.reddit.com/r/threejs/comments/wdqkhu/looking_for_performance_improvement_consultation/#:~:text=Works%20fine%20on%20Chrome.,%E2%80%A2%204y%20ago

[3] Dynamic Resolution Scaler - Claude Code Skill for R3F. Opens in new tab.  
https://mcpmarket.com/tools/skills/dynamic-resolution-scaler-3#:~:text=bydeadronos,generative%20art%20or%20data%20visualizations

[4] Building Efficient Three.js Scenes: Optimize Performance .... Opens in new tab.  
https://tympanus.net/codrops/2025/02/11/building-efficient-three-js-scenes-optimize-performance-while-maintaining-quality/#:~:text=In%20this%20case%2C%20the%20behavior,deeper%20into%20this%20topic%20later.

[5] Integrating Three.js with React: A Comprehensive ... - Medium. Opens in new tab.  
https://medium.com/@alfinohatta/integrating-three-js-278774d45973

[6] How to enable retina resolution render.setSize on iPhone with threejs. Opens in new tab.  
https://stackoverflow.com/questions/60500710/how-to-enable-retina-resolution-render-setsize-on-iphone-with-threejs#:~:text=You%20may%20not%20want%20to,appropriate%20to%20not%20set%20it.

[7] Scaling performance - React Three Fiber. Opens in new tab.  
https://r3f.docs.pmnd.rs/advanced/scaling-performance#:~:text=It%20gives%20you%20a%20factor,performance%20changes%20on%20their%20own.

[8] Looking for Performance Improvement Consultation : r/threejs. Opens in new tab.  
https://www.reddit.com/r/threejs/comments/wdqkhu/looking_for_performance_improvement_consultation/#:~:text=Works%20fine%20on%20Chrome.,%E2%80%A2%204y%20ago

[9] Dynamic Resolution Scaler - Claude Code Skill for R3F. Opens in new tab.  
https://mcpmarket.com/tools/skills/dynamic-resolution-scaler-3#:~:text=bydeadronos,generative%20art%20or%20data%20visualizations

[10] Building Efficient Three.js Scenes: Optimize Performance .... Opens in new tab.  
https://tympanus.net/codrops/2025/02/11/building-efficient-three-js-scenes-optimize-performance-while-maintaining-quality/#:~:text=In%20this%20case%2C%20the%20behavior,deeper%20into%20this%20topic%20later.

[11] Integrating Three.js with React: A Comprehensive ... - Medium. Opens in new tab.  
https://medium.com/@alfinohatta/integrating-three-js-278774d45973

[12] How to enable retina resolution render.setSize on iPhone with threejs. Opens in new tab.  
https://stackoverflow.com/questions/60500710/how-to-enable-retina-resolution-render-setsize-on-iphone-with-threejs#:~:text=You%20may%20not%20want%20to,appropriate%20to%20not%20set%20it.

[13] Scaling performance - React Three Fiber. Opens in new tab.  
https://r3f.docs.pmnd.rs/advanced/scaling-performance#:~:text=It%20gives%20you%20a%20factor,performance%20changes%20on%20their%20own.

[14] Looking for Performance Improvement Consultation : r/threejs. Opens in new tab.  
https://www.reddit.com/r/threejs/comments/wdqkhu/looking_for_performance_improvement_consultation/#:~:text=Works%20fine%20on%20Chrome.,%E2%80%A2%204y%20ago

[15] Dynamic Resolution Scaler - Claude Code Skill for R3F. Opens in new tab.  
https://mcpmarket.com/tools/skills/dynamic-resolution-scaler-3#:~:text=bydeadronos,generative%20art%20or%20data%20visualizations

[16] Building Efficient Three.js Scenes: Optimize Performance .... Opens in new tab.  
https://tympanus.net/codrops/2025/02/11/building-efficient-three-js-scenes-optimize-performance-while-maintaining-quality/#:~:text=In%20this%20case%2C%20the%20behavior,deeper%20into%20this%20topic%20later.

[17] Integrating Three.js with React: A Comprehensive ... - Medium. Opens in new tab.  
https://medium.com/@alfinohatta/integrating-three-js-278774d45973

[18] How to enable retina resolution render.setSize on iPhone with threejs. Opens in new tab.  
https://stackoverflow.com/questions/60500710/how-to-enable-retina-resolution-render-setsize-on-iphone-with-threejs#:~:text=You%20may%20not%20want%20to,appropriate%20to%20not%20set%20it.

