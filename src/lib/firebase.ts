import { initializeApp, type FirebaseApp } from 'firebase/app'
import { getAnalytics, isSupported } from 'firebase/analytics'
import { getAuth, GoogleAuthProvider, type Auth } from 'firebase/auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || 'AIzaSyCHkKh3amAmHAXGiEHU0btPHaheOoZD9As',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || 'ai-marketer-242f8.firebaseapp.com',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'ai-marketer-242f8',
  storageBucket:
    import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || 'ai-marketer-242f8.firebasestorage.app',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '497042168374',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '1:497042168374:web:7ff29012e80fb6b33bd697',
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || 'G-QXF69TEKET',
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
