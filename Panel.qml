import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import qs.Ui

Panel {
    id: root
    moduleName: "diky.mouse"
    ipcTarget: "diky.mouse"
    manageIpc: false
    implicitWidth: icon.implicitWidth
    implicitHeight: icon.implicitHeight
    property var mice: []
    property string selectedName: ""
    property var draft: ({sensitivity: 0, scroll_factor: 1, accel_profile: "adaptive", left_handed: false, natural_scroll: false, buttons: {}})
    property int selectedButton: 274
    property var pressedButtons: ({})
    property var flashUntil: ({})
    property string statusKey: ""
    property string errorText: ""
    property bool dirty: false
    readonly property bool busy: backend.running
    readonly property var mouse: { for (var i=0; i<mice.length; i++) if (mice[i].name === selectedName) return mice[i]; return null }
    readonly property var actionIds: ["default", "back", "forward", "copy", "paste", "undo", "disabled"]
    Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
    function buttonName(code) { return strings.t(({272:"left",273:"right",274:"middle",275:"back",276:"forward"})[code] || "middle") }
    function change(key, value) { var next = Object.assign({}, draft); next[key]=value; draft=next; dirty=true; statusKey="pending"; errorText="" }
    function assign(action) { var next=Object.assign({},draft.buttons || {}); next[String(selectedButton)]=action; change("buttons",next) }
    function request(action, extra) {
        if (backend.running) return
        backend.command = ["python3", decodeURIComponent(String(Qt.resolvedUrl("backend.py")).replace(/^file:\/\//, "")),action].concat(extra || [])
        backend.running=true
    }
    function watch() {
        if (watcher.running) { watchAgain.restart(); return }
        watcher.command=["python3",decodeURIComponent(String(Qt.resolvedUrl("backend.py")).replace(/^file:\/\//, "")),"watch",root.opened ? selectedName : ""]
        watcher.running=true
    }
    function select(name) {
        selectedName=name; pressedButtons={}; dirty=false; statusKey=""; errorText=""
        if (mouse) draft=JSON.parse(JSON.stringify(mouse.profile))
        watch()
    }
    function refresh() { request("list") }
    function reset() { draft={sensitivity:0,scroll_factor:1,accel_profile:"adaptive",left_handed:false,natural_scroll:false,buttons:{}}; dirty=true; statusKey="pending" }
    Commons.ShellIpc {
        target: "diky.mouse"
        function open(): void { root.open() }
        function close(): void { root.close() }
        function toggle(): void { root.toggle() }
        function selectMouse(name: string): void { for (var i=0;i<root.mice.length;i++) if(root.mice[i].name===name) { root.select(name); return } }
        function snapshot(): string { return JSON.stringify({opened:root.opened, selected:root.selectedName, mice:root.mice.length, pressed:root.pressedButtons, error:root.errorText, dirty:root.dirty}) }
        function buttonEvent(device: string, code: int, down: bool): void {
            if (!root.opened || device !== root.selectedName || code < 272 || code > 276) return
            if (!down) return
            var next=Object.assign({},root.pressedButtons); next[String(code)]=true; root.pressedButtons=next
            var deadlines=Object.assign({},root.flashUntil); deadlines[String(code)]=Date.now()+220; root.flashUntil=deadlines
        }
    }
    onOpenedChanged: { if (opened) refresh(); else { pressedButtons={}; watch() } }
    Component.onDestruction: Quickshell.execDetached(["hyprctl","eval","_G.diky_mouse_watch = ''"])
    Timer {
        interval: 40; repeat: true; running: root.opened
        onTriggered: {
            var next=Object.assign({},root.pressedButtons); var changed=false
            for (var key in next) if(next[key] && Date.now() >= (root.flashUntil[key] || 0)) { next[key]=false; changed=true }
            if(changed) root.pressedButtons=next
        }
    }
    Timer { id: watchAgain; interval: 150; onTriggered: root.watch() }
    Process { id: watcher }
    Process {
        id: backend
        property string output: ""
        stdout: StdioCollector { onStreamFinished: backend.output=text }
        onExited: function(code, status) {
            try {
                var data=JSON.parse(output)
                if (!data.ok) { root.errorText=data.error || "Unknown error"; return }
                root.mice=data.mice || []
                var found=false
                for (var i=0; i<root.mice.length; i++) if (root.mice[i].name === root.selectedName) found=true
                var wasSave=command[2] === "save"
                var chosen=found ? root.selectedName : (root.mice.length ? root.mice[0].name : "")
                root.select(chosen)
                if (wasSave) root.statusKey="saved"
            } catch(e) { root.errorText=String(e) }
        }
    }
    BarIconButton { id: icon; anchors.fill: parent; bar: root.bar; text: "󰍽"; tooltipText: strings.t("title"); onPressed: root.toggle() }
    KeyboardPanel {
        id: popup
        anchorItem: icon; owner: root; bar: root.bar; open: root.opened
        contentWidth: fittedContentWidth(Commons.Style.space(390))
        contentHeight: fittedContentHeight(loadedContentHeight)
        focusTarget: loadedContent
        content: FocusScope {
            implicitHeight: Math.min(column.implicitHeight, Commons.Style.space(720))
            Keys.onEscapePressed: root.close()
            Flickable {
                anchors.fill: parent; contentHeight: column.implicitHeight; clip: true
                boundsBehavior: Flickable.StopAtBounds
            Column {
                id: column; width: parent.width; spacing: Commons.Style.space(9)
                Label { text: strings.t("title"); font.pixelSize: Commons.Style.font.title; font.bold: true }
                Label { visible: !!root.mouse; text: root.mouse ? root.mouse.label : ""; font.pixelSize: Commons.Style.font.subtitle; opacity: .75 }
                Label { visible: !root.mouse; text: strings.t("none") }
                Column {
                    width: parent.width; visible: !!root.mouse; spacing: Commons.Style.space(9)
                    MousePicture {
                        width: parent.width; implicitHeight: Commons.Style.space(170)
                        pressedButtons: root.pressedButtons; selectedButton: root.selectedButton
                        availableButtons: root.mouse ? root.mouse.buttons : []
                        onPicked: function(code) { root.selectedButton=code }
                    }
                    Label { text: strings.t("hint"); font.pixelSize: Commons.Style.font.caption; opacity: .7 }
                    Label { text: strings.t("assignment").arg(root.buttonName(root.selectedButton)); font.bold: true }
                    Flow {
                        visible: root.selectedButton >= 274; width: parent.width; spacing: Commons.Style.space(5)
                        Repeater {
                            model: root.actionIds
                            Button {
                                required property string modelData
                                text: strings.t(modelData === "back" ? "backAction" : modelData === "forward" ? "forwardAction" : modelData)
                                selected: (root.draft.buttons[String(root.selectedButton)] || "default") === modelData
                                bordered: true; focusable: true
                                enabled: !root.busy && !!root.mouse && root.mouse.buttons.indexOf(root.selectedButton)>=0
                                onClicked: root.assign(modelData)
                            }
                        }
                    }
                    Label { visible: root.selectedButton < 274; text: strings.t("primaryHint"); opacity: .7 }
                    PanelSeparator { foreground: Commons.Color.foreground }
                    Label { text: strings.t("speedValue").arg(Commons.I18n.formatNumber(Math.round(speed.liveValue*100))); font.bold: true }
                    PanelSlider { id: speed; width: parent.width; bar: root.bar; minimum: -1; maximum: 1; step: .05; value: root.draft.sensitivity; enabled: !root.busy; onReleased: function(v) { root.change("sensitivity",Math.round(v*100)/100) } }
                    Row {
                        spacing: Commons.Style.space(6)
                        Button { text: strings.t("acceleration") + ": " + strings.t(root.draft.accel_profile === "flat" ? "flat" : "adaptive"); bordered: true; focusable: true; enabled: !root.busy; onClicked: root.change("accel_profile",root.draft.accel_profile === "flat" ? "adaptive" : "flat") }
                    }
                    Label { text: strings.t("scroll").arg(Commons.I18n.formatNumber(scroll.liveValue,1)) }
                    PanelSlider { id: scroll; width: parent.width; bar: root.bar; minimum: .1; maximum: 3; step: .1; value: root.draft.scroll_factor; enabled: !root.busy; onReleased: function(v) { root.change("scroll_factor",Math.round(v*10)/10) } }
                    Flow {
                        width: parent.width; spacing: Commons.Style.space(5)
                        Button { text: strings.t("natural"); selected: root.draft.natural_scroll; bordered: true; focusable: true; enabled: !root.busy; onClicked: root.change("natural_scroll",!root.draft.natural_scroll) }
                        Button { text: strings.t("swap"); selected: root.draft.left_handed; bordered: true; focusable: true; enabled: !root.busy; onClicked: root.change("left_handed",!root.draft.left_handed) }
                    }
                    Label { text: strings.t("dpi"); font.pixelSize: Commons.Style.font.caption; opacity: .6 }
                }
                Flow {
                    width: parent.width; spacing: Commons.Style.space(6)
                    Button { text: strings.t("apply"); selected: true; bordered: true; focusable: true; enabled: root.dirty && !root.busy && !!root.mouse; onClicked: root.request("save",[root.selectedName,JSON.stringify(root.draft)]) }
                    Button { text: strings.t("reset"); bordered: true; focusable: true; enabled: !root.busy && !!root.mouse; onClicked: root.reset() }
                    Button { text: strings.t("refresh"); bordered: true; focusable: true; enabled: !root.busy; onClicked: root.refresh() }
                }
                Label { text: root.errorText ? strings.t("error").arg(root.errorText) : root.busy ? strings.t("busy") : root.statusKey ? strings.t(root.statusKey) : strings.t("desktop"); font.pixelSize: Commons.Style.font.caption; opacity: .75 }
            }
            }
        }
    }
    component Label: Text {
        width: parent.width
        textFormat: Text.PlainText
        color: Commons.Color.foreground
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        wrapMode: Text.WordWrap
    }
}
