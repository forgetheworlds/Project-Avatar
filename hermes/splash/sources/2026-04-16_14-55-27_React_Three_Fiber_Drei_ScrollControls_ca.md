To create a scroll-driven camera animation in React Three Fiber, you use the `<ScrollControls>` component from the Drei library along with the `useScroll` and `useFrame` hooks. This setup allows you to map the user's scroll progress (a value from 0 to 1) directly to camera properties like position, rotation, or focal length. `[11][12][13][14][15]`

Core Implementation 

1. **Wrap your scene**: Place your components inside `<ScrollControls>` within the `<Canvas>`. The `pages` prop defines the total scrollable height in viewports.
2. **Access scroll data**: Inside a sub-component, use the `useScroll()` hook to get real-time data like `offset` (current position) and `delta` (scroll speed).
3. **Update the camera**: Use `useFrame` to update the camera every frame. The `damp` function from Three.js is often used to ensure the movement is smooth and non-linear. `[6][7][8][9][10]`

Example Code  jsx

``` import { ScrollControls, useScroll } from '@react-three/drei' import { useFrame } from '@react-three/fiber' import { useRef } from 'react' function Scene() { const scroll = useScroll() useFrame((state, delta) => {
    // scroll.offset is a value between 0 and 1 const offset = scroll.offset
  
    // Smoothly animate camera position based on scroll state.camera.position.z = 5 + offset * 10 state.camera.lookAt(0, 0, 0)
  }) return <mesh>...</mesh>
} function App() { return (
    <Canvas>
      <ScrollControls pages={3} damping={0.1}>
        <Scene />
      </ScrollControls>
    </Canvas>
  )
}

```

Use code with caution.

Copied to clipboard

Key Techniques 

* **Damping**: The `damping` prop on `<ScrollControls>` adds inertia to the scroll, making the camera movement feel professional and "heavy" rather than jerky.
* **Range-based triggers**: Use `scroll.range(start, end)` to trigger specific animations only during a certain portion of the total scroll height (e.g., between page 1 and 2).
* **Camera Tracking**: For more complex paths, you can animate a "target" object and have the camera use `lookAt` toward that target while it moves along a spline. `[1][2][3][4][5]`

Watch these tutorials to see different ways of implementing smooth scroll-driven camera paths:

07:58

[React Three Fiber tutorial - Scroll Animations Wawa SenseiYouTube](https://www.youtube.com/watch?v=pXpckHDDNYo&t=0s)

35:49

[Tutorial for 3D model scroll animation in website | React ... Techy Web DevYouTube](https://www.youtube.com/watch?v=lrsB-4SN4us&t=0s)

1 min

[This 3D Scroll Animation is INSANE Thanks to Three.js (3D ... CodegridYouTube](https://www.youtube.com/watch?v=rbIbvw6c53k&t=21&t=21s)

If you'd like to refine this, let me know: 

* Do you want the camera to follow a **pre-defined path** (spline)?
* Are you looking to use a **timeline library** like GSAP alongside Drei?
* Should the camera **focus on different objects** as you scroll? 

I can provide a more tailored code snippet for those specific needs. 

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

[1] ScrollControls - Drei. Opens in new tab.  
https://drei.docs.pmnd.rs/controls/scroll-controls#:~:text=You%20can%20listen%20and%20react,is%20reached%20const%20a%20=%20data.

[2] How do you animate the camera with react-three-fiber?. Opens in new tab.  
https://stackoverflow.com/questions/75562296/how-do-you-animate-the-camera-with-react-three-fiber

[3] Scroll-driven camera animation - Brad Woods Digital Garden. Opens in new tab.  
https://garden.bradwoods.io/notes/javascript/three-js/scroll-driven-camera-animation#:~:text=When%20enabled%2C%20the%20page%20enters%20a%20dev,to%20the%20console%20whenever%20the%20camera%20moves.

[4] Scroll - Wawa Sensei. Opens in new tab.  
https://wawasensei.dev/courses/react-three-fiber/lessons/scroll#:~:text=In%20HTML%20the%20page%20scroll,ScrollControls%20from%20Drei%20perfectly%20does.

[5] AMB-Coders/react-three-fiber-drei - GitHub. Opens in new tab.  
https://github.com/AMB-Coders/react-three-fiber-drei#:~:text=ScrollControls,-type%20ScrollControlsProps%20=%20%7B%20/**&text=Scroll%20controls%20create%20a%20HTML,in%20or%20out%20of%20view.

[6] ScrollControls - Drei. Opens in new tab.  
https://drei.docs.pmnd.rs/controls/scroll-controls#:~:text=You%20can%20listen%20and%20react,is%20reached%20const%20a%20=%20data.

[7] How do you animate the camera with react-three-fiber?. Opens in new tab.  
https://stackoverflow.com/questions/75562296/how-do-you-animate-the-camera-with-react-three-fiber

[8] Scroll-driven camera animation - Brad Woods Digital Garden. Opens in new tab.  
https://garden.bradwoods.io/notes/javascript/three-js/scroll-driven-camera-animation#:~:text=When%20enabled%2C%20the%20page%20enters%20a%20dev,to%20the%20console%20whenever%20the%20camera%20moves.

[9] Scroll - Wawa Sensei. Opens in new tab.  
https://wawasensei.dev/courses/react-three-fiber/lessons/scroll#:~:text=In%20HTML%20the%20page%20scroll,ScrollControls%20from%20Drei%20perfectly%20does.

[10] AMB-Coders/react-three-fiber-drei - GitHub. Opens in new tab.  
https://github.com/AMB-Coders/react-three-fiber-drei#:~:text=ScrollControls,-type%20ScrollControlsProps%20=%20%7B%20/**&text=Scroll%20controls%20create%20a%20HTML,in%20or%20out%20of%20view.

[11] ScrollControls - Drei. Opens in new tab.  
https://drei.docs.pmnd.rs/controls/scroll-controls#:~:text=You%20can%20listen%20and%20react,is%20reached%20const%20a%20=%20data.

[12] How do you animate the camera with react-three-fiber?. Opens in new tab.  
https://stackoverflow.com/questions/75562296/how-do-you-animate-the-camera-with-react-three-fiber

[13] Scroll-driven camera animation - Brad Woods Digital Garden. Opens in new tab.  
https://garden.bradwoods.io/notes/javascript/three-js/scroll-driven-camera-animation#:~:text=When%20enabled%2C%20the%20page%20enters%20a%20dev,to%20the%20console%20whenever%20the%20camera%20moves.

[14] Scroll - Wawa Sensei. Opens in new tab.  
https://wawasensei.dev/courses/react-three-fiber/lessons/scroll#:~:text=In%20HTML%20the%20page%20scroll,ScrollControls%20from%20Drei%20perfectly%20does.

[15] AMB-Coders/react-three-fiber-drei - GitHub. Opens in new tab.  
https://github.com/AMB-Coders/react-three-fiber-drei#:~:text=ScrollControls,-type%20ScrollControlsProps%20=%20%7B%20/**&text=Scroll%20controls%20create%20a%20HTML,in%20or%20out%20of%20view.

