import QtQuick

// A picture on the art ground (spec §7: pictures always sit on surfaceArt), or a quiet crown while there is none,
// it has not come yet, or it could not be had. ExerciseStore keeps each picture on the device once it has come; the
// binding reads its revision so it asks again when one lands.
Rectangle {
    id: frame

    // The picture's name (the catalog's), or "" for none.
    property string name: ""
    property int fillMode: Image.PreserveAspectCrop
    readonly property string source: frame.name.length > 0 && ExerciseStore.pictureRevision >= 0
                                     ? ExerciseStore.pictureUrl(frame.name) : ""

    color: Preferences.surfaceArt
    radius: Preferences.cornerRadius
    clip: true

    Image {
        id: image
        objectName: "picture"
        anchors.fill: parent
        source: frame.source
        fillMode: frame.fillMode
        asynchronous: true
        visible: status === Image.Ready
    }

    Image {
        objectName: "picturePlaceholder"
        anchors.centerIn: parent
        width: Math.min(frame.width, frame.height) * 0.35
        height: width
        source: "qrc:/icons/prideAppIcon.png"
        fillMode: Image.PreserveAspectFit
        opacity: 0.22
        visible: image.status !== Image.Ready
    }
}
