import { useAuth } from "../contexts/AuthContext";
import { LayoutDashboard, User, LogOut } from "lucide-react";

export function DashboardPage() {
  const { user, logout } = useAuth();

  const handleLogout = () => {
    void logout().catch((error) => {
      console.error("Logout failed", error);
    });
  };

  return (
    <div>
      <div className="mb-8 flex items-center space-x-4">
        <div className="w-14 h-14 bg-purple-600 rounded-full flex items-center justify-center">
          <User className="h-8 w-8 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Welcome back!</h1>
          <p className="text-gray-600">{user?.email || "Guest"}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-center space-x-4 mb-4">
            <div className="p-3 bg-purple-100 rounded-lg">
              <LayoutDashboard className="h-8 w-8 text-purple-600" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900">Overview</h3>
          </div>
          <p className="text-gray-600">Your dashboard overview and statistics</p>
        </div>

        <div className="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-center space-x-4 mb-4">
            <div className="p-3 bg-purple-100 rounded-lg">
              <User className="h-8 w-8 text-purple-600" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900">Profile</h3>
          </div>
          <p className="text-gray-600">Manage your account settings</p>
        </div>

        <div className="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-shadow">
          <div className="flex items-center space-x-4 mb-4">
            <div className="p-3 bg-purple-100 rounded-lg">
              <LogOut className="h-8 w-8 text-purple-600" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900">Session</h3>
          </div>
          <p className="text-gray-600 mb-4">You are currently logged in</p>
          <button
            type="button"
            onClick={handleLogout}
            className="w-full flex items-center justify-center space-x-2 border-2 border-red-500 text-red-600 font-medium py-2 px-4 rounded-lg hover:bg-red-50 transition-colors"
          >
            <LogOut className="h-4 w-4" />
            <span>Logout</span>
          </button>
        </div>
      </div>
    </div>
  );
}
