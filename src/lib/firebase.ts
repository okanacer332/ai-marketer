import { initializeApp, type FirebaseApp } from 'firebase/app'
import { getAnalytics, isSupported } from 'firebase/analytics'
import { getAuth, GoogleAuthProvider, type Auth } from 'firebase/auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
}

const requiredFirebaseFields = [
  firebaseConfig.apiKey,
  firebaseConfig.authDomain,
  firebaseConfig.projectId,
  firebaseConfig.appId,
]

const hasInvalidPlaceholder = requiredFirebaseFields.some(
  (value) => !value || value.startsWith('your_'),
)

export const firebaseReady = !hasInvalidPlaceholder

export let firebaseInitError: string | null = null
export let app: FirebaseApp | null = null
export let auth: Auth | null = null
export let googleProvider: GoogleAuthProvider | null = null

if (firebaseReady) {
  try {
    app = initializeApp(firebaseConfig)
    auth = getAuth(app)
    googleProvider = new GoogleAuthProvider()
    googleProvider.setCustomParameters({
      prompt: 'select_account',
    })

    if (typeof window !== 'undefined' && firebaseConfig.measurementId) {
      void isSupported().then((supported) => {
        if (supported && app) {
          getAnalytics(app)
        }
      })
    }
  } catch {
    firebaseInitError =
      'Firebase yapılandırması geçersiz olduğu için giriş şu an kullanılamıyor.'
  }
} else {
  firebaseInitError = 'Firebase yapılandırması eksik olduğu için giriş şu an kullanılamıyor.'
}
