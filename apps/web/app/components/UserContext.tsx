"use client";

import { createContext, useContext } from "react";

import type { User } from "../lib/api";

const UserContext = createContext<User | null>(null);

export const UserProvider = UserContext.Provider;

export function useUser(): User {
  const user = useContext(UserContext);
  if (!user) throw new Error("useUser must be used inside the app shell");
  return user;
}
