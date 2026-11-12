allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
// Optional acceptance toolchain; shared SDK and plugin sources remain untouched.
val acceptanceNdk = providers.environmentVariable("YUNO_ANDROID_NDK_VERSION").orNull
if (acceptanceNdk != null) {
    require(acceptanceNdk == "27.1.12297006") { "Unsupported acceptance NDK" }
    subprojects {
        plugins.withId("com.android.library") {
            extensions.getByType<com.android.build.api.variant.LibraryAndroidComponentsExtension>().finalizeDsl {
                it.ndkVersion = acceptanceNdk
                it.externalNativeBuild.cmake.version = "3.22.1"
                it.defaultConfig.externalNativeBuild.cmake.arguments.add("-DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON")
            }
        }
    }
}

subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
