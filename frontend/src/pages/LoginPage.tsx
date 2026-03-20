import { useNavigate, Link } from "react-router-dom";
import { LoginForm } from "../components/LoginForm";

export function LoginPage() {
  const navigate = useNavigate();
  return (
    <div>
      <LoginForm onSuccess={() => navigate("/dashboard")} />
      <p className="mt-6 text-center text-sm text-gray-600">
        Don't have an account?{" "}
        <Link
          to="/register"
          className="font-medium text-purple-600 hover:text-purple-700 transition-colors"
        >
          Register
        </Link>
      </p>
    </div>
  );
}
