"use client";

import "./login.css";

export default function LoginPage() {
  return (
    <div className="login-container">
      <div className="login-card">
        <h1 className="login-title">Apparatus Ebooks</h1>
        <a href="/auth/login" className="login-button">
          Log in or sign up
        </a>
      </div>
    </div>
  );
}
