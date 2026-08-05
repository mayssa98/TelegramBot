plugins {
    id("com.android.application")
}

android {
    namespace = "app.blackmarket.botcontrol"
    compileSdk = 35

    defaultConfig {
        applicationId = "app.blackmarket.botcontrol"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
}
