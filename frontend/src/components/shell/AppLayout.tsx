import { Outlet } from "react-router-dom";
import { Navbar } from "./Navbar";

export function AppLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="mx-auto max-w-[1600px] px-4 py-4 sm:px-6 sm:py-6 lg:py-8">
        <Outlet />
      </main>
    </div>
  );
}
