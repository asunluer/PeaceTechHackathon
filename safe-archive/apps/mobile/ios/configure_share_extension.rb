#!/usr/bin/env ruby
# One-time project setup for the share_handler iOS text/URL extension.
require 'xcodeproj'

root = File.expand_path(__dir__)
project = Xcodeproj::Project.open(File.join(root, 'Runner.xcodeproj'))
runner = project.targets.find { |target| target.name == 'Runner' }
raise 'Runner target missing' unless runner

unless project.targets.any? { |target| target.name == 'ShareExtension' }
  extension = project.new_target(:app_extension, 'ShareExtension', :ios, '13.0')
  group = project.main_group.new_group('ShareExtension', 'ShareExtension')
  source = group.new_file('ShareViewController.swift')
  group.new_file('Info.plist')
  group.new_file('ShareExtension.entitlements')
  extension.source_build_phase.add_file_reference(source)
  extension.build_configurations.each do |config|
    config.build_settings.merge!({
      'PRODUCT_BUNDLE_IDENTIFIER' => 'org.safearchive.safeArchive.ShareExtension',
      'PRODUCT_NAME' => '$(TARGET_NAME)',
      'INFOPLIST_FILE' => 'ShareExtension/Info.plist',
      'CODE_SIGN_ENTITLEMENTS' => 'ShareExtension/ShareExtension.entitlements',
      'SWIFT_VERSION' => '5.0',
      'IPHONEOS_DEPLOYMENT_TARGET' => '13.0',
      'TARGETED_DEVICE_FAMILY' => '1,2',
      'GENERATE_INFOPLIST_FILE' => 'NO',
      'APPLICATION_EXTENSION_API_ONLY' => 'YES',
      'SKIP_INSTALL' => 'YES',
    })
  end
  runner.add_dependency(extension)
  phase = runner.new_copy_files_build_phase('Embed App Extensions')
  phase.dst_subfolder_spec = '13'
  phase.add_file_reference(extension.product_reference, true)
end

runner.build_configurations.each do |config|
  config.build_settings['CODE_SIGN_ENTITLEMENTS'] = 'Runner/Runner.entitlements'
  config.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = '13.0'
end
project.save
