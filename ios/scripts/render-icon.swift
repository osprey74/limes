// Renders the gauge icon (design canvas, option C) to PNG, from the same
// figures as android/app/src/main/res/drawable/ic_launcher_foreground.xml
// (a 108 grid whose inner 72 is the icon).
//
//   swift scripts/render-icon.swift      (run in ios/)
//
// Writes the app icon (1024, on the ground color, the inner 72 of the grid)
// and the launch-screen gauge (the whole grid at 192 pt, transparent).
import AppKit
import CoreGraphics

func color(_ hex: UInt32) -> CGColor {
    CGColor(red: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255, alpha: 1)
}

/// `window` is the square of the 108 grid that fills the image.
func render(pixels: Int, window: CGRect, background: CGColor?, to path: String) {
    let context = CGContext(
        data: nil, width: pixels, height: pixels, bitsPerComponent: 8, bytesPerRow: 0,
        space: CGColorSpace(name: CGColorSpace.sRGB)!,
        bitmapInfo: (background == nil ? CGImageAlphaInfo.premultipliedLast : CGImageAlphaInfo.noneSkipLast).rawValue
    )!
    if let background {
        context.setFillColor(background)
        context.fill(CGRect(x: 0, y: 0, width: pixels, height: pixels))
    }
    // The grid's y runs down.
    let scale = CGFloat(pixels) / window.width
    context.translateBy(x: 0, y: CGFloat(pixels))
    context.scaleBy(x: scale, y: -scale)
    context.translateBy(x: -window.minX, y: -window.minY)
    context.setLineCap(.round)

    let center = CGPoint(x: 54, y: 58)
    func arc(from: CGFloat, to: CGFloat, _ stroke: CGColor) {
        context.addArc(center: center, radius: 24, startAngle: from * .pi / 180, endAngle: to * .pi / 180, clockwise: false)
        context.setStrokeColor(stroke)
        context.setLineWidth(6)
        context.strokePath()
    }
    func line(_ a: CGPoint, _ b: CGPoint, _ stroke: CGColor, width: CGFloat) {
        context.move(to: a)
        context.addLine(to: b)
        context.setStrokeColor(stroke)
        context.setLineWidth(width)
        context.strokePath()
    }
    arc(from: 135, to: 405, color(0x4A525E)) // the scale
    arc(from: 135, to: 270, color(0x34D3B8)) // the part covered
    line(CGPoint(x: 66.73, y: 45.27), CGPoint(x: 75.21, y: 36.79), color(0xD7262E), width: 4) // the limit
    line(center, CGPoint(x: 47.84, y: 41.08), color(0xF2F4F7), width: 3.5) // the needle
    context.setFillColor(color(0xF2F4F7))
    context.fillEllipse(in: CGRect(x: 50, y: 54, width: 8, height: 8))

    let png = NSBitmapImageRep(cgImage: context.makeImage()!).representation(using: .png, properties: [:])!
    try! png.write(to: URL(fileURLWithPath: path))
    print(path)
}

let assets = "Limes/Assets.xcassets"
render(pixels: 1024, window: CGRect(x: 18, y: 18, width: 72, height: 72), background: color(0x0B0D10),
       to: "\(assets)/AppIcon.appiconset/icon-1024.png")
for scale in 1...3 {
    render(pixels: 192 * scale, window: CGRect(x: 0, y: 0, width: 108, height: 108), background: nil,
           to: "\(assets)/Gauge.imageset/gauge@\(scale)x.png")
}
