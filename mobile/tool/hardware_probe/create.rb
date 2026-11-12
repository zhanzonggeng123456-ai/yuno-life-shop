require 'xcodeproj'
require 'fileutils'
root = File.expand_path(ARGV.fetch(0))
FileUtils.mkdir_p(root)
source = ARGV[1] == '--control' ? 'Control.swift' : 'Probe.swift'
FileUtils.cp(File.join(__dir__, source), File.join(root, 'Probe.swift'))
p = Xcodeproj::Project.new(File.join(root, 'YunoHardwareProbe.xcodeproj'))
t = p.new_target(:ui_test_bundle, 'YunoHardwareProbe', :ios, '15.0')
f = p.main_group.new_file('Probe.swift')
t.source_build_phase.add_file_reference(f)
t.build_configurations.each do |c|
 c.build_settings.merge!({
 'PRODUCT_BUNDLE_IDENTIFIER'=>'com.yunolife.shop.hardwareprobe',
 'PRODUCT_NAME'=>'$(TARGET_NAME)', 'SWIFT_VERSION'=>'5.0',
 'SDKROOT'=>'iphoneos', 'SUPPORTED_PLATFORMS'=>'iphoneos',
 'TARGETED_DEVICE_FAMILY'=>'1', 'GENERATE_INFOPLIST_FILE'=>'YES',
 'CODE_SIGN_STYLE'=>'Automatic', 'CODE_SIGN_IDENTITY'=>'Apple Development',
 'DEVELOPMENT_TEAM'=>ENV.fetch('YUNO_DEVELOPMENT_TEAM')
 })
end
p.save
s = Xcodeproj::XCScheme.new
s.add_build_target(t)
s.add_test_target(t)
s.test_action.build_configuration = 'Debug'
s.save_as(p.path, 'YunoHardwareProbe', true)
