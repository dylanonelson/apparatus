"use client";

import { useState } from "react";
import { useUser } from "@auth0/nextjs-auth0/client";
import "./UserMenu.css";

type UserType = NonNullable<ReturnType<typeof useUser>["user"]>;

interface UserMenuProps {
  user: UserType;
}

export function UserMenu({ user }: UserMenuProps) {
  const [isOpen, setIsOpen] = useState(false);

  const getInitials = (name?: string | null) => {
    if (!name) return "U";
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const getLoginMethod = (user: UserType) => {
    const sub = user.sub;
    if (!sub) return "Unknown";

    if (sub.startsWith("auth0|")) return "Email/Password";
    if (sub.startsWith("google-oauth2|")) return "Google";
    if (sub.startsWith("github|")) return "GitHub";
    if (sub.startsWith("facebook|")) return "Facebook";

    return "SSO";
  };

  return (
    <div
      className="user-menu-container"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <div className="user-avatar">
        {user.picture ? (
          <img src={user.picture} alt={user.name || "User"} />
        ) : (
          <span className="user-initials">{getInitials(user.name)}</span>
        )}
      </div>

      {isOpen && (
        <div className="user-menu-dropdown">
          <div className="user-menu-info">
            <div className="user-menu-email">{user.email}</div>
            <div className="user-menu-method">{getLoginMethod(user)}</div>
          </div>
          <div className="user-menu-divider" />
          <a href="/auth/logout" className="user-menu-logout">
            Log out
          </a>
        </div>
      )}
    </div>
  );
}
