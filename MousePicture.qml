import QtQuick
import qs.Commons as Commons

Item {
    id: root
    property var pressedButtons: ({})
    property int selectedButton: 274
    property var availableButtons: [272, 273, 274, 275, 276]
    property color ink: Commons.Color.foreground
    property color accent: Commons.Color.accent
    property color paper: Commons.Color.background
    signal picked(int code)
    implicitHeight: 206
    // Vector shapes stay crisp at every scale and can respond to physical clicks.
    Item {
        width: 300; height: 206; scale: 0.8; transformOrigin: Item.Top
        anchors.horizontalCenter: parent.horizontalCenter
        Rectangle { x: 75; y: 28; width: 181; height: 172; radius: 72; color: root.ink; opacity: 0.14; rotation: -9 }
        Rectangle {
            x: 64; y: 18; width: 182; height: 174; radius: 70; rotation: -9
            color: Qt.tint(root.paper, Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.12))
            border.color: root.ink; border.width: 3
        }
        // Thumb trackball, the unmistakable ERGO silhouette.
        Rectangle {
            x: 34; y: 94; width: 83; height: 83; radius: 42
            color: root.accent; border.color: root.ink; border.width: 3
            Rectangle { x: 15; y: 12; width: 28; height: 16; radius: 8; color: "white"; opacity: .4; rotation: -30 }
            Rectangle { x: 54; y: 53; width: 7; height: 7; radius: 4; color: root.ink; opacity: .25 }
        }
        Repeater {
            model: [
                {code:272,x:119,y:22,w:48,h:78,r:20,angle:-9},
                {code:273,x:178,y:25,w:51,h:79,r:22,angle:-9},
                {code:274,x:164,y:40,w:15,h:41,r:7,angle:-9},
                {code:275,x:77,y:64,w:27,h:16,r:7,angle:-26},
                {code:276,x:101,y:43,w:27,h:16,r:7,angle:-26}
            ]
            Rectangle {
                required property var modelData
                readonly property bool available: root.availableButtons.indexOf(modelData.code) >= 0
                readonly property bool down: root.pressedButtons[String(modelData.code)] === true
                x: modelData.x; y: modelData.y; width: modelData.w; height: modelData.h
                radius: modelData.r; rotation: modelData.angle
                color: down ? root.accent : hit.containsMouse ? Qt.tint(root.paper, Qt.rgba(root.accent.r,root.accent.g,root.accent.b,.35)) : root.paper
                border.width: root.selectedButton === modelData.code ? 3 : 2
                border.color: root.selectedButton === modelData.code ? root.accent : root.ink
                opacity: available ? 1 : .25
                scale: down ? .93 : 1
                Behavior on color { ColorAnimation { duration: 75 } }
                Behavior on scale { NumberAnimation { duration: 75 } }
                MouseArea {
                    id: hit; anchors.fill: parent; hoverEnabled: true
                    enabled: parent.available; cursorShape: Qt.PointingHandCursor
                    onClicked: root.picked(modelData.code)
                }
            }
        }
        // A little comic flourish on the palm rest.
        Text { x: 139; y: 132; text: "• ᴗ •"; textFormat: Text.PlainText; color: root.ink; font.pixelSize: 23; rotation: -9; opacity: .65 }
        Rectangle { x: 127; y: 164; width: 57; height: 3; radius: 2; rotation: -9; color: root.ink; opacity: .15 }
    }
}
