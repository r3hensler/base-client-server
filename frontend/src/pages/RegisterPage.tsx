import { useNavigate, Link } from "react-router-dom";
import { RegisterForm } from "../components/RegisterForm";

export function RegisterPage() {
  const navigate = useNavigate();
  return (
    <div>
      <RegisterForm onSuccess={() => navigate("/login")} />
      <p>
        Already have an account? <Link to="/login">Login</Link>
      </p>
    </div>
  );
}
