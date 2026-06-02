import React, { createContext, useContext, useReducer, useEffect, useState, type ReactNode } from "react";

export type PetState = "idle" | "happy" | "think" | "curious" | "excite" | "sleep";

interface PetStateValue {
  state: PetState;
  dispatch: React.Dispatch<PetAction>;
  triggerAction: (action: PetAction) => void;
  morphId: string;
  setMorphId: (id: string) => void;
}

type PetAction =
  | { type: "SET_STATE"; payload: PetState }
  | { type: "IDLE" }
  | { type: "HAPPY" }
  | { type: "THINK" }
  | { type: "CURIOUS" }
  | { type: "EXCITE" }
  | { type: "SLEEP" }
  | { type: "TOGGLE" };

const PetContext = createContext<PetStateValue | null>(null);

const petStateReducer = (state: PetState, action: PetAction): PetState => {
  switch (action.type) {
    case "SET_STATE":
      return action.payload;
    case "IDLE":
      return "idle";
    case "HAPPY":
      return "happy";
    case "THINK":
      return "think";
    case "CURIOUS":
      return "curious";
    case "EXCITE":
      return "excite";
    case "SLEEP":
      return "sleep";
    default:
      return state;
  }
};

interface PetProviderProps {
  children: ReactNode;
}

let lastUserActionTime = Date.now();
const SLEEP_TIMEOUT = 120000; // 2 min idle → sleep

export const PetProvider: React.FC<PetProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(petStateReducer, "idle");
  const [morphId, setMorphId] = useState("rocky");

  // Auto-idle after 3s of state change
  useEffect(() => {
    if (state === "sleep") return;

    const timer = setTimeout(() => {
      const timeSinceLastAction = Date.now() - lastUserActionTime;
      if (timeSinceLastAction < SLEEP_TIMEOUT) {
        dispatch({ type: "IDLE" });
      } else {
        dispatch({ type: "SLEEP" });
      }
    }, 3000);

    return () => clearTimeout(timer);
  }, [state]);

  // Sleep check loop
  useEffect(() => {
    const interval = setInterval(() => {
      const timeSinceLastAction = Date.now() - lastUserActionTime;
      if (timeSinceLastAction >= SLEEP_TIMEOUT && state !== "sleep") {
        dispatch({ type: "SLEEP" });
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [state]);

  const triggerAction = (action: PetAction) => {
    lastUserActionTime = Date.now();
    dispatch(action);
  };

  return (
    <PetContext.Provider value={{ state, dispatch, triggerAction, morphId, setMorphId }}>
      {children}
    </PetContext.Provider>
  );
};

export const usePet = () => {
  const context = useContext(PetContext);
  if (!context) {
    throw new Error("usePet must be used within PetProvider");
  }
  return context;
};

// Export actions for easy usage
export const petActions = {
  setIdle: () => ({ type: "IDLE" as const }),
  setHappy: () => ({ type: "HAPPY" as const }),
  setThink: () => ({ type: "THINK" as const }),
  setCurious: () => ({ type: "CURIOUS" as const }),
  setExcite: () => ({ type: "EXCITE" as const }),
  setSleep: () => ({ type: "SLEEP" as const }),
};
