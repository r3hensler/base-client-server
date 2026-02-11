import { useAuth } from "../contexts/AuthContext";

export function DashboardPage() {
  const { user, logout } = useAuth();

  const handleLogout = () => {
    void logout().catch((error) => {
      console.error("Logout failed", error);
    });
  };

  return (
    <div>
      <h1>Dashboard</h1>
      <p>Welcome, {user?.email}</p>
      <button onClick={handleLogout}>Logout</button>
    </div>
  );
}
