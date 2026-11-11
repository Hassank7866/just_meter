import React from 'react';
import { VehicleViolationSummary } from '../api/client';
import { Modal } from './Modal';

interface ChallanModalProps {
  challan: VehicleViolationSummary | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenNotificationModal?: (challan: VehicleViolationSummary) => void;
  onOpenWhatsAppSettings?: () => void;
}

// Official documents come only from persisted cases.
export const ChallanModal: React.FC<ChallanModalProps> = ({ challan, isOpen, onClose }) => {
  if (!challan) return null;
  return <Modal isOpen={isOpen} onClose={onClose} title="Challan case review">
    <div className="p-4 space-y-3"><p>{challan.plate_number} has {challan.total_violations} recorded violations.</p>
      <p>Review and approve a draft in the case register before issuing or sending a document.</p>
      <button className="btn-primary px-3 py-2" onClick={() => {
        window.dispatchEvent(new CustomEvent('justmeter:challan', { detail: { vehicleId: challan.database_vehicle_id } }));
        onClose();
      }}>Open case register</button>
    </div>
  </Modal>;
};
