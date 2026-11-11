import React from 'react';
import { TwinReference } from '../api/client';

export const VehicleProfileLink: React.FC<{ reference: TwinReference }> = ({ reference }) => (
  <button type="button" className="block text-xs text-sky-400 hover:text-sky-200 underline mt-1"
    onClick={() => window.dispatchEvent(new CustomEvent('justmeter:vehicle-profile', { detail: reference }))}>
    View vehicle profile
  </button>
);
