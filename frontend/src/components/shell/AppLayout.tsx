import { Outlet } from "react-router-dom";
import { useState } from "react";
import { Navbar, type Role } from "./Navbar";

export function AppLayout() {
  const [role, setRole] = useState<Role>("Finance Admin");
  return (
    <div className="min-h-screen bg-background">
      <Navbar role={role} onRoleChange={setRole} />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
