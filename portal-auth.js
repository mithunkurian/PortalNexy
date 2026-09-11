// ─── Firebase config ───────────────────────────────────────────
const firebaseConfig = {
  apiKey:            "AIzaSyDnvusSFiEiV24qy_tVxdLpj_QR4FFWQvU",
  authDomain:        "portalnexy.firebaseapp.com",
  projectId:         "portalnexy",
  storageBucket:     "portalnexy.firebasestorage.app",
  messagingSenderId: "387758302623",
  appId:             "1:387758302623:web:c8f69186baa92a889c09aa",
};
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const db   = firebase.firestore();
const googleProvider = new firebase.auth.GoogleAuthProvider();

const ALLOWED_EMAIL = "mithunkurian@gmail.com";

auth.onAuthStateChanged(user => {
  const loginScreen = document.getElementById('login-screen');
  const portalApp   = document.getElementById('portal-app');
  const loadingEl   = document.getElementById('login-loading');
  if (loadingEl) loadingEl.classList.add('hidden');

  if (user) {
    if (ALLOWED_EMAIL !== "YOUR_GOOGLE_EMAIL@gmail.com" && user.email !== ALLOWED_EMAIL) {
      auth.signOut();
      showLoginError("Access denied. Only the Founder's account is authorised.");
      return;
    }
    loginScreen.classList.add('hidden');
    portalApp.classList.remove('hidden');
    updateUserProfile(user);
    startFirestoreListeners();
    init();
  } else {
    stopFirestoreListeners();
    loginScreen.classList.remove('hidden');
    portalApp.classList.add('hidden');
  }
});

function updateUserProfile(user) {
  const nameEl   = document.getElementById('user-name');
  const avatarEl = document.getElementById('user-avatar');
  if (nameEl) nameEl.textContent = user.displayName || user.email;
  if (avatarEl) {
    if (user.photoURL) {
      avatarEl.innerHTML = `<img src="${user.photoURL}" class="w-full h-full object-cover rounded-full" />`;
    } else {
      const initials = (user.displayName || 'MK').split(' ').map(n=>n[0]).join('').slice(0,2).toUpperCase();
      avatarEl.textContent = initials;
    }
  }
}

function signInWithGoogle() {
  const btn = document.getElementById('google-signin-btn');
  btn.disabled = true;
  btn.innerHTML = `<span class="material-symbols-outlined text-[16px] animate-spin" style="animation-duration:0.8s">progress_activity</span> Signing in…`;
  hideLoginError();
  auth.signInWithPopup(googleProvider).catch(err => {
    btn.disabled = false;
    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/><path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/><path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z"/></svg> Sign in with Google`;
    showLoginError(err.code === 'auth/popup-closed-by-user' ? 'Sign-in window closed. Please try again.' : err.message);
  });
}

function signOutUser() { auth.signOut(); }

function showLoginError(msg) {
  const el    = document.getElementById('login-error');
  const msgEl = document.getElementById('login-error-msg');
  if (msgEl) msgEl.textContent = msg;
  if (el) el.classList.remove('hidden');
}

function hideLoginError() {
  const el = document.getElementById('login-error');
  if (el) el.classList.add('hidden');
}
