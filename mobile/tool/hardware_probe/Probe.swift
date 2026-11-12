import XCTest

final class YunoHardwareProbe: XCTestCase {
    func testReadInstalledApp() throws {
        continueAfterFailure = false
        let app = XCUIApplication(bundleIdentifier: "com.yunolife.shop.dev")
        app.launch()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 20))
        XCTAssertTrue(app.buttons.firstMatch.waitForExistence(timeout: 20))
        let state = XCTAttachment(string: app.debugDescription)
        state.name = "Yuno installed app accessibility"
        state.lifetime = .keepAlways
        add(state)
        let picture = XCTAttachment(screenshot: app.screenshot())
        picture.name = "Yuno installed app real device"
        picture.lifetime = .keepAlways
        add(picture)
    }
}
