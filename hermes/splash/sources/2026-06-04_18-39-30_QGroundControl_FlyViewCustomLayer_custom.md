To create a custom drone overlay in QGroundControl (QGC) using `FlyViewCustomLayer.qml`, you must use **resource overrides** within a custom build directory. This additive layer lets you draw custom UI elements over the map/video stream without modifying the upstream source code. ``

Development Pipeline Step-by-Step 

1. **Setup Custom Folder**: Clean your build directory, duplicate the `custom-example` folder in the QGC root directory, and rename it to `custom`.
2. **Generate Resources**: Navigate into `/custom` and run the script `python update_qrc.py` to target resource exclusions.
3. **Override QML File**: Create your replacement `FlyViewCustomLayer.qml` file inside your custom resources path.
4. **Compile App**: Build the project via Qt Creator or CMake to apply changes. ``