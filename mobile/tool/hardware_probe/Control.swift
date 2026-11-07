import XCTest
// Official XCTest actions; the command channel uses only this runner's Documents directory.
// No network listener and no changes to the shipping App are required.
final class YunoHardwareProbe: XCTestCase {
 let directory=FileManager.default.urls(for:.documentDirectory,in:.userDomainMask)[0]
 func request(_ path:String,_ body:[String:Any]?=nil)->[String:Any] {
  if let body=body {
   var data=body
   let id=data["id"] as? String ?? "unknown"
   if let png=data.removeValue(forKey:"png") as? String, let bytes=Data(base64Encoded:png) {try? bytes.write(to:directory.appendingPathComponent(id+".png"),options:.atomic)}
   if let bytes=try? JSONSerialization.data(withJSONObject:data) {try? bytes.write(to:directory.appendingPathComponent(id+".json"),options:.atomic)}
   return [:]
  }
  guard let d=try? Data(contentsOf:directory.appendingPathComponent("command.json")),let value=(try? JSONSerialization.jsonObject(with:d)) as? [String:Any] else {return [:]}
  return value
 }
 func testReadInstalledApp() throws {
  continueAfterFailure=false
  var last=request("/next")["id"] as? String ?? ""
  _=request("/result",["id":"ready","state":"connected"])
  let deadline=Date().addingTimeInterval(1800)
  while Date()<deadline {
   let c=request("/next");guard let id=c["id"] as? String else {Thread.sleep(forTimeInterval:0.3);continue}
   guard id.range(of:"^[A-Za-z0-9_-]+$",options:.regularExpression) != nil else {continue}
   if id==last {Thread.sleep(forTimeInterval:0.3);continue};last=id
   let bundle=c["bundle"] as? String ?? "com.yunolife.shop.dev"
   guard ["com.yunolife.shop.dev","com.apple.camera","com.apple.mobileslideshow","com.apple.springboard"].contains(bundle) else {continue}
   let app=XCUIApplication(bundleIdentifier:bundle)
   let op=c["op"] as? String ?? "dump"
   if op=="finish" {_=request("/result",["id":id,"state":"finished"]);return}
   var state="ok";var fieldValue:String?
   if op=="activate" {app.activate()}
   else if op=="tapPoint",let x=c["x"] as? Double,let y=c["y"] as? Double {app.coordinate(withNormalizedOffset:CGVector(dx:0,dy:0)).withOffset(CGVector(dx:x,dy:y)).tap()}
   else if op=="typeFocused",let value=c["value"] as? String {app.typeText(value)}
   else if op=="swipeUp" {app.swipeUp()}
   else if op=="swipeDown" {app.swipeDown()}
   else if op=="tap" || op=="type" || op=="clear" || op=="press" || op=="replace" {
    let type=c["type"] as? String ?? "button"
    let q:XCUIElementQuery
    switch type {case "text":q=app.staticTexts;case "field":q=app.textFields;case "secure":q=app.secureTextFields;case "cell":q=app.cells;case "image":q=app.images;case "other":q=app.otherElements;case "key":q=app.keys;case "menu":q=app.menuItems;case "any":q=app.descendants(matching:.any);default:q=app.buttons}
    var query=q
    if let label=c["label"] as? String {query=q.matching(NSPredicate(format:c["contains"] as? Bool == true ? "label CONTAINS %@":"label == %@",label))}
    let e=query.element(boundBy:c["index"] as? Int ?? 0)
    if e.waitForExistence(timeout:5) && e.isHittable && e.isEnabled {
     if op=="press" {e.press(forDuration:1.2)} else {e.tap()}
     if op=="replace",let value=c["value"] as? String {e.typeKey("a",modifierFlags:.command);e.typeText(value);fieldValue=e.value as? String}
     if op=="type",let value=c["value"] as? String {e.typeText(value)}
     if op=="clear" {e.typeKey("a",modifierFlags:.command);e.typeText(XCUIKeyboardKey.delete.rawValue)}
    } else {state="element unavailable"}
   }
   Thread.sleep(forTimeInterval:c["wait"] as? Double ?? 0.7)
   var result:[String:Any]=["id":id,"state":state,"ax":app.debugDescription]
   if let fieldValue=fieldValue {result["fieldValue"]=fieldValue}
   result["png"]=app.screenshot().pngRepresentation.base64EncodedString()
   _=request("/result",result)
  }
  XCTFail("Control session timed out without an explicit finish command")
 }
}
