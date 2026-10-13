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

const googleProvider = new firebase.auth.GoogleAuthProvider();

const ALLOWED_EMAIL = "mithunkurian@gmail.com";

auth.onAuthStateChanged(user => {
  const signInButton = document.getElementById('google-signin-btn');
  signInButton.disabled = false;
  signInButton.textContent = 'Sign in with Google';
  const loginScreen = document.getElementById('login-screen');
  const portalApp   = document.getElementById('portal-app');
  const loadingEl   = document.getElementById('login-loading');
  if (loadingEl) loadingEl.classList.add('hidden');

  if (user) {
    if (user.email !== ALLOWED_EMAIL) {
      loginScreen.classList.remove('hidden');
      portalApp.classList.add('hidden');
      auth.signOut();
      showLoginError("Access denied. Only the Founder's account is authorised.");
      return;
    }
    loginScreen.classList.add('hidden');
    portalApp.classList.remove('hidden');
    updateUserProfile(user);
  } else {
    toggleSidebar(false);
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
      const photo = document.createElement("img");
      photo.src = user.photoURL;
      photo.alt = "";
      avatarEl.replaceChildren(photo);
    } else {
      const initials = (user.displayName || 'MK').split(' ').map(n=>n[0]).join('').slice(0,2).toUpperCase();
      avatarEl.textContent = initials;
    }
  }
}

function signInWithGoogle() {
  const btn = document.getElementById('google-signin-btn');
  btn.disabled = true;
  btn.textContent = 'Signing in…';
  hideLoginError();
  auth.signInWithPopup(googleProvider).catch(err => {
    btn.disabled = false;
    btn.textContent = 'Sign in with Google';
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
