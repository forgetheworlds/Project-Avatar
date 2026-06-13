To inject a custom drone control widget into QGroundControl (QGC) using `FlyViewCustomLayer.qml`, you must leverage QGC’s **Resource Override System**. This allows you to place additive UI elements (buttons, custom sliders, payload controls) cleanly over the map/video layer without editing the core QGC code. 

Here is a comprehensive guide to building and integrating your custom plugin layer in QGroundControl (v4/v5 architecture). 

---

Step 1: Initialize the Custom Directory Structure 

QGC uses a system where a folder named `custom` overrides upstream resources. 

1. Go to your QGroundControl root source directory.
2. Rename the boilerplate `custom.example` folder to `custom`.
3. Create the directory path for your custom FlyView component:  
`custom/res/qml/QGroundControl/FlightDisplay/` 

Step 2: Implement `FlyViewCustomLayer.qml` `[1][2][3][4][5][6]`

Create a file named `FlyViewCustomLayer.qml` inside that new folder. This layout exposes tool insets to prevent your custom widget from overlapping with core QGC joysticks or toolbars.  qml

``` import QtQuick import QGroundControl import QGroundControl.Controls

// Placeholder for custom FlyView layer (full implementation in)
Item { id: _root property var parentToolInsets
  
    // Custom widget example
    Rectangle { width: 200; height: 120 anchors.right: parent.right anchors.top: parent.top anchors.margins: 20 anchors.topMargin: parentToolInsets.rightEdgeTopInset + 10 color: QGroundControl.globalPalette.window opacity: 0.85
  
        QGCButton { text: "Action" anchors.centerIn: parent onClicked: { /* Trigger action */ }
        }
    }
}

```

Use code with caution.

Step 3: Register the Resource Override 

QGC must be told to ignore its default `FlyViewCustomLayer.qml` and compile yours instead. 

1. Open your `custom/custom.qrc` file.
2. Add your layer under the matching virtual prefix path:
  xml
  

```
<qresource prefix="/res">
    <file alias="QGroundControl/FlightDisplay/FlyViewCustomLayer.qml">res/qml/QGroundControl/FlightDisplay/FlyViewCustomLayer.qml</file>
</qresource>

```
  Use code with caution.

3. Run the automatic resource update script in the `custom` folder. 

Step 4: Rebuild the Project 

Clean your previous build assets and recompile to apply the custom resource mapping. 

---

UI Layer Architecture Reference 

When designing custom widgets, keep in mind the visual Z-index hierarchy: 

* **`FlyViewCustomLayer.qml` (Top Layer):** Custom widgets, payloads, and buttons.
* **`FlyViewWidgetsOverlay.qml` (Middle):** Core QGC panels (Compass, Telemetry).
* **`FlyView.qml` (Base Layer):** Base map and video streams. 

For further customization, C++ backend bindings can be created to handle custom MAVLink messages. 

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

[1] Customizing QGroundControl - RIIS. Opens in new tab.  
https://www.riis.com/blog/customizing-qgroundcontrol

[2] Fly View Customization | QGC Guide (4.3). Opens in new tab.  
https://docs.qgroundcontrol.com/Stable_V4.3/en/qgc-dev-guide/custom_build/fly_view.html

[3] Customizing Qgroundcontrol. Opens in new tab.  
https://www.youtube.com/watch?v=uLRdDl5a-Yk&t=475

[4] Fly View Customization | QGC Guide (v5.0). Opens in new tab.  
https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-dev-guide/custom_build/fly_view.html

[5] Fly View Customization | QGC Guide (v5.0). Opens in new tab.  
https://docs.qgroundcontrol.com/Stable_V5.0/zh/qgc-dev-guide/custom_build/fly_view.html

[6] Customizing QGroundControl v5. Opens in new tab.  
https://www.youtube.com/watch?v=Kfhzu24rIJc&t=774

