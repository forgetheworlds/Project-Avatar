In React Three Fiber (R3F), optimizing performance for large assets typically involves combining **Draco** for geometry compression and **KTX2** for GPU-resident texture compression. 

1. Geometry Optimization: Draco Compression `[7][8][9][10][11][12]`

Draco can reduce geometry file sizes by 90-95%. Decompression runs in a Web Worker, preventing main-thread freezes. 

* **Setup**: Use the `useGLTF` hook from @react-three/drei.
* **Decoder Path**: You must provide a path to the Draco decoder files, typically hosted in your `public` folder.  jsx

``` import { useGLTF } from '@react-three/drei' function Model() {
  // Set the path to where your draco binaries are located (e.g., /draco/) const { scene } = useGLTF('/model.glb', '/draco/') return <primitive object={scene} />
}

// Global preloading (outside the component) useGLTF.preload('/model.glb', '/draco/')

```

Use code with caution.

Copied to clipboard

2. Texture Optimization: KTX2 

Unlike JPEG/PNG, KTX2 textures stay compressed in VRAM, significantly reducing memory usage and preventing mobile browser crashes. 

* **Implementation**: Use the `useKTX2` hook from `@react-three/drei`.
* **Transcoder**: Requires a transcoder (e.g., Basis Universal) to convert KTX2 to your specific GPU's format.  jsx

``` import { useKTX2 } from '@react-three/drei' function Scene() { const texture = useKTX2('/texture.ktx2') return (
    <mesh>
      <boxGeometry />
      <meshStandardMaterial map={texture} />
    </mesh>
  )
}

// Preload to fetch and parse immediately useKTX2.preload('/texture.ktx2')

```

Use code with caution.

Copied to clipboard

3. Preloading & Advanced Optimization 

Preloading ensures assets are fetched before they are needed in the scene, which is critical for smooth transitions. 

* **Preloading Hooks**: All major hooks (`useGLTF`, `useTexture`, `useKTX2`) have a `.preload()` method that should be called at the top level of your file.
* **GPU Upload**: Preloading only fetches and parses; the actual upload to the GPU occurs when the object enters the camera's view. To force an early GPU upload, use the `<Preload all />` component from `@react-three/drei`.
* **Optimization Pipeline**: Use tools like gltf-transform to process your models before loading:  
`gltf-transform optimize input.glb output.glb --texture-compress ktx2 --compress draco`. 

Comparison Table: Draco vs. KTX2 

| Feature `[1][2][3][4][5][6]` | Draco | KTX2 |
| --- | --- | --- |
| **Primary Target** | Geometry (meshes/vertices) | Textures (images) |
| **Size Benefit** | Reduces download size significantly | Reduces VRAM (GPU memory) footprint |
| **Runtime Benefit** | Faster parsing on CPU | Prevents GPU crashes and reduces lag |
| **Tooling** | `gltf-pipeline`, `gltf-transform` | `KTX-Software`, `gltf-transform` |

If you'd like, let me know: 

* If you are seeing **performance lag** or **memory crashes** (especially on mobile)
* The **size of your assets** currently
* If you need help setting up the **decoder/transcoder paths** in your project 

I can help you debug specific loading issues or refine your optimization command. 

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

[1] How to preload the texture and assets upfront before using it?. Opens in new tab.  
https://discourse.threejs.org/t/how-to-preload-the-texture-and-assets-upfront-before-using-it/46802#:~:text=Due%20to%20this%20problem%20my,tries%20to%20get%20the%20data.&text=there%20is%20a%20component%20for,end%20up%20in%20a%20fallback.&text=this%20could%20be%20a%20bad,to%20do%20that%20pre%2Demptively.&text=Really%20Thanks%20for%20the%20code%20snippet.

[2] 100 Three.js Tips That Actually Improve Performance (2026). Opens in new tab.  
https://www.utsubo.com/blog/threejs-best-practices-100-tips

[3] Fix Loading Model Freezes with Three.js & React. Opens in new tab.  
https://wawasensei.dev/tuto/fix-loading-model-freezes-threejs-react-ktx2#:~:text=Imagine%20spending%20weeks%20building%20a,%2Dtransform%20and%20KTX%2DSoftware.

[4] Optimizing 3D Models for the Web using Draco and other tools. Opens in new tab.  
https://www.axl-devhub.me/blog/optimizing-3d-models#:~:text=Always%20convert%20to%20GLB%20format,fallbacks%20for%20low%2Dend%20devices

[5] KTX2Loader – three.js docs. Opens in new tab.  
https://threejs.org/docs/pages/KTX2Loader.html#:~:text=A%20loader%20for%20KTX%202.0,BasisU%20HDR

[6] How to add both KTX2Loader and DracoLoader for .... Opens in new tab.  
https://discourse.threejs.org/t/how-to-add-both-ktx2loader-and-dracoloader-for-compressed-glb/46726#:~:text=Gundeep_Singh%20January%2010%2C%202023%2C%2012,in%20the%20onLoad()%20callback.

[7] How to preload the texture and assets upfront before using it?. Opens in new tab.  
https://discourse.threejs.org/t/how-to-preload-the-texture-and-assets-upfront-before-using-it/46802#:~:text=Due%20to%20this%20problem%20my,tries%20to%20get%20the%20data.&text=there%20is%20a%20component%20for,end%20up%20in%20a%20fallback.&text=this%20could%20be%20a%20bad,to%20do%20that%20pre%2Demptively.&text=Really%20Thanks%20for%20the%20code%20snippet.

[8] 100 Three.js Tips That Actually Improve Performance (2026). Opens in new tab.  
https://www.utsubo.com/blog/threejs-best-practices-100-tips

[9] Fix Loading Model Freezes with Three.js & React. Opens in new tab.  
https://wawasensei.dev/tuto/fix-loading-model-freezes-threejs-react-ktx2#:~:text=Imagine%20spending%20weeks%20building%20a,%2Dtransform%20and%20KTX%2DSoftware.

[10] Optimizing 3D Models for the Web using Draco and other tools. Opens in new tab.  
https://www.axl-devhub.me/blog/optimizing-3d-models#:~:text=Always%20convert%20to%20GLB%20format,fallbacks%20for%20low%2Dend%20devices

[11] KTX2Loader – three.js docs. Opens in new tab.  
https://threejs.org/docs/pages/KTX2Loader.html#:~:text=A%20loader%20for%20KTX%202.0,BasisU%20HDR

[12] How to add both KTX2Loader and DracoLoader for .... Opens in new tab.  
https://discourse.threejs.org/t/how-to-add-both-ktx2loader-and-dracoloader-for-compressed-glb/46726#:~:text=Gundeep_Singh%20January%2010%2C%202023%2C%2012,in%20the%20onLoad()%20callback.

