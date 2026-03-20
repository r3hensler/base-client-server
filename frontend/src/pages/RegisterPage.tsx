import { useNavigate, Link } from "react-router-dom";
import { RegisterForm } from "../components/RegisterForm";

export function RegisterPage() {
  const navigate = useNavigate();
  return (
    <div>
      <RegisterForm onSuccess={() => navigate("/login")} />
      <p className="mt-6 text-center text-sm text-gray-600">
        Already have an account?{" "}
        <Link
          to="/login"
          className="font-medium text-purple-600 hover:text-purple-700 transition-colors"
        >
          Login
        </Link>
      </p>
    </div>
  );
}
