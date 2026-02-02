"""
Monitoring service that implements the hierarchical oversight system.
Council Members monitor Lead Agents, Lead Agents monitor Task Agents.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.models.entities.agents import Agent, AgentType, LeadAgent, TaskAgent, CouncilMember
from backend.models.entities.monitoring import (
    AgentHealthReport, ViolationReport, ViolationSeverity, 
    TaskVerification, PerformanceMetric, MonitoringAlert
)
from backend.models.entities.task import Task, SubTask, TaskStatus
from backend.models.database import get_db_context, get_next_agentium_id

class MonitoringService:
    """
    Implements the checks and balances monitoring system.
    Higher-tier agents actively supervise lower-tier agents.
    """
    
    @staticmethod
    def conduct_health_check(monitor_id: str, subject_id: str, db: Session) -> AgentHealthReport:
        """
        Monitor agent evaluates subordinate agent health.
        Called periodically by the monitoring agent.
        """
        monitor = db.query(Agent).filter_by(id=monitor_id).first()
        subject = db.query(Agent).filter_by(id=subject_id).first()
        
        if not monitor or not subject:
            raise ValueError("Monitor or subject not found")
        
        # Check hierarchy permission
        if subject.parent_id != monitor.id:
            # Council can monitor any Lead (they're all under Head)
            if not (monitor.agent_type == AgentType.COUNCIL_MEMBER and subject.agent_type == AgentType.LEAD_AGENT):
                raise PermissionError("Monitor does not have authority over this subject")
        
        # Calculate metrics
        recent_tasks = db.query(Task).filter(
            Task.assigned_task_agent_ids.contains(subject.agentium_id),
            Task.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).all()
        
        total = len(recent_tasks)
        completed = len([t for t in recent_tasks if t.status == TaskStatus.COMPLETED])
        failed = len([t for t in recent_tasks if t.status == TaskStatus.FAILED])
        success_rate = (completed / total * 100) if total > 0 else 100
        
        # Check for violations
        violations = db.query(ViolationReport).filter_by(
            violator_agent_id=subject_id,
            status="open"
        ).count()
        
        # Determine status
        status = "healthy"
        if violations > 0:
            status = "violation_detected"
        elif success_rate < 50:
            status = "degraded"
        elif failed > 3:
            status = "degraded"
        
        # Generate findings
        findings = []
        if success_rate < 80:
            findings.append(f"Low success rate: {success_rate}%")
        if violations > 0:
            findings.append(f"{violations} open violations")
        if subject.status.value == "suspended":
            findings.append("Agent is currently suspended")
        
        health_score = max(0, min(100, success_rate - (violations * 10)))
        
        report = AgentHealthReport(
            monitor_agent_id=monitor_id,
            monitor_agentium_id=monitor.agentium_id,
            subject_agent_id=subject_id,
            subject_agentium_id=subject.agentium_id,
            status=status,
            overall_health_score=health_score,
            task_success_rate=success_rate,
            constitution_violations_count=violations,
            findings=findings,
            recommendations=MonitoringService._generate_recommendations(status, findings)
        )
        
        db.add(report)
        db.commit()
        
        # Auto-escalate critical issues
        if status == "violation_detected" and violations >= 3:
            MonitoringService._escalate_to_head(report, db)
        
        return report
    
    @staticmethod
    def report_violation(
        reporter_id: str,
        violator_id: str,
        severity: ViolationSeverity,
        violation_type: str,
        description: str,
        evidence: List[Dict],
        db: Session
    ) -> ViolationReport:
        """
        File a violation report against a subordinate.
        """
        reporter = db.query(Agent).filter_by(id=reporter_id).first()
        violator = db.query(Agent).filter_by(id=violator_id).first()
        
        if not reporter or not violator:
            raise ValueError("Reporter or violator not found")
        
        # Check permission to report
        if violator.parent_id != reporter.id:
            if not (reporter.agent_type == AgentType.COUNCIL_MEMBER and violator.agent_type == AgentType.LEAD_AGENT):
                raise PermissionError("No authority to report this agent")
        
        report = ViolationReport(
            reporter_agent_id=reporter_id,
            reporter_agentium_id=reporter.agentium_id,
            violator_agent_id=violator_id,
            violator_agentium_id=violator.agentium_id,
            severity=severity,
            violation_type=violation_type,
            description=description,
            evidence=evidence,
            context={
                "reporter_type": reporter.agent_type.value,
                "violator_type": violator.agent_type.value,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        db.add(report)
        db.commit()
        
        # Auto-suspend for critical violations
        if severity == ViolationSeverity.CRITICAL:
            violator.status = "suspended"
            db.commit()
            
            # Create alert
            MonitoringService._create_alert(
                alert_type="critical_violation",
                severity=severity,
                detected_by=reporter_id,
                affected=violator_id,
                message=f"Critical violation by {violator.agentium_id}: {violation_type}",
                db=db
            )
        
        # Route to appropriate authority
        if violator.agent_type == AgentType.LEAD_AGENT:
            # Council Members investigate Leads
            council = db.query(CouncilMember).first()
            if council:
                report.assign_investigation(council.agentium_id)
        elif violator.agent_type == AgentType.COUNCIL_MEMBER:
            # Head of Council investigates Council Members
            head = db.query(Agent).filter_by(agent_type=AgentType.HEAD_OF_COUNCIL).first()
            if head:
                report.assign_investigation(head.agentium_id)
        
        db.commit()
        return report
    
    @staticmethod
    def verify_task_completion(
        lead_id: str,
        task_agent_id: str,
        task_id: str,
        output: str,
        output_data: Dict,
        db: Session
    ) -> TaskVerification:
        """
        Lead Agent verifies Task Agent's work before finalizing.
        """
        verification = TaskVerification(
            task_id=task_id,
            task_agent_id=task_agent_id,
            lead_agent_id=lead_id,
            submitted_output=output,
            submitted_data=output_data,
            submitted_at=datetime.utcnow(),
            checks_performed=[
                "constitution_compliance",
                "output_accuracy",
                "requirement_fulfillment"
            ]
        )
        
        # Automated checks would happen here
        # In real implementation, Lead Agent AI would analyze output
        
        db.add(verification)
        db.commit()
        
        return verification
    
    @staticmethod
    def calculate_performance_metrics(
        monitor_id: str,
        subject_id: str,
        db: Session,
        period_days: int = 7
    ) -> PerformanceMetric:
        """
        Calculate rolling performance metrics for a subordinate.
        Used to identify trends and trigger training/termination.
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=period_days)
        
        # Get task stats
        tasks = db.query(Task).filter(
            Task.assigned_task_agent_ids.contains(db.query(Agent).filter_by(id=subject_id).first().agentium_id),
            Task.created_at.between(start_date, end_date)
        ).all()
        
        assigned = len(tasks)
        completed = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
        failed = len([t for t in tasks if t.status == TaskStatus.FAILED])
        
        # Check for rejections (verifications that failed)
        agent = db.query(Agent).filter_by(id=subject_id).first()
        rejected = db.query(TaskVerification).filter_by(
            task_agent_id=subject_id,
            verification_status="rejected"
        ).count()
        
        metric = PerformanceMetric(
            agent_id=subject_id,
            calculated_by_agent_id=monitor_id,
            period_start=start_date,
            period_end=end_date,
            tasks_assigned=assigned,
            tasks_completed=completed,
            tasks_failed=failed,
            tasks_rejected=rejected,
            avg_quality_score=(completed / max(assigned, 1)) * 100,
            constitution_violations=db.query(ViolationReport).filter_by(
                violator_agent_id=subject_id
            ).count()
        )
        
        # Determine trend
        previous = db.query(PerformanceMetric).filter_by(
            agent_id=subject_id
        ).order_by(PerformanceMetric.period_end.desc()).first()
        
        metric.trend = metric.calculate_trend(previous)
        
        # Generate recommendation
        if metric.avg_quality_score and metric.avg_quality_score < 60:
            metric.recommended_action = "retrain"
        elif metric.constitution_violations > 3:
            metric.recommended_action = "terminate"
        elif metric.avg_quality_score and metric.avg_quality_score > 95 and metric.trend == "improving":
            metric.recommended_action = "promote"
        else:
            metric.recommended_action = "monitor"
        
        db.add(metric)
        db.commit()
        
        # Auto-terminate recommendation triggers alert
        if metric.recommended_action == "terminate":
            MonitoringService._create_alert(
                alert_type="termination_recommended",
                severity=ViolationSeverity.MAJOR,
                detected_by=monitor_id,
                affected=subject_id,
                message=f"Agent {agent.agentium_id} recommended for termination due to poor performance",
                db=db
            )
        
        return metric
    
    @staticmethod
    def get_monitoring_dashboard(monitor_id: str, db: Session) -> Dict[str, Any]:
        """
        Get overview of all subordinates for a monitoring agent.
        Shows health reports, violations, and pending verifications.
        """
        monitor = db.query(Agent).filter_by(id=monitor_id).first()
        
        if not monitor:
            raise ValueError("Monitor not found")
        
        # Get subordinates based on hierarchy
        if monitor.agent_type == AgentType.HEAD_OF_COUNCIL:
            subjects = db.query(Agent).filter(
                Agent.agent_type.in_([AgentType.COUNCIL_MEMBER, AgentType.LEAD_AGENT])
            ).all()
        elif monitor.agent_type == AgentType.COUNCIL_MEMBER:
            subjects = db.query(Agent).filter_by(
                agent_type=AgentType.LEAD_AGENT
            ).all()
        elif monitor.agent_type == AgentType.LEAD_AGENT:
            subjects = monitor.subordinates  # Direct children
        else:
            subjects = []
        
        dashboard = {
            "monitor": monitor.agentium_id,
            "subordinate_count": len(subjects),
            "subordinates": []
        }
        
        for subject in subjects:
            latest_health = db.query(AgentHealthReport).filter_by(
                subject_agent_id=subject.id
            ).order_by(AgentHealthReport.created_at.desc()).first()
            
            open_violations = db.query(ViolationReport).filter_by(
                violator_agent_id=subject.id,
                status="open"
            ).count()
            
            pending_verifications = 0
            if monitor.agent_type == AgentType.LEAD_AGENT:
                pending_verifications = db.query(TaskVerification).filter_by(
                    lead_agent_id=monitor_id,
                    verification_status="pending"
                ).count()
            
            dashboard["subordinates"].append({
                "agentium_id": subject.agentium_id,
                "name": subject.name,
                "status": subject.status.value,
                "health": latest_health.to_dict() if latest_health else None,
                "open_violations": open_violations,
                "pending_verifications": pending_verifications
            })
        
        return dashboard
    
    @staticmethod
    def _generate_recommendations(status: str, findings: List[str]) -> str:
        """Generate recommendation text based on health status."""
        if status == "healthy":
            return "Continue standard monitoring"
        elif status == "degraded":
            return "Increase monitoring frequency, investigate performance issues"
        elif status == "violation_detected":
            return "Review violations and consider retraining or escalation"
        else:
            return "Immediate attention required"
    
    @staticmethod
    def _escalate_to_head(report: AgentHealthReport, db: Session):
        """Escalate critical health report to Head of Council."""
        head = db.query(Agent).filter_by(agent_type=AgentType.HEAD_OF_COUNCIL).first()
        if head:
            report.escalate_to_head(
                head.agentium_id,
                f"Multiple violations detected in {report.subject_agentium_id}"
            )
            db.commit()
    
    @staticmethod
    def _create_alert(
        alert_type: str,
        severity: ViolationSeverity,
        detected_by: str,
        affected: Optional[str],
        message: str,
        db: Session
    ):
        """Create monitoring alert."""
        agent = db.query(Agent).filter_by(id=detected_by).first()
        
        alert = MonitoringAlert(
            alert_type=alert_type,
            severity=severity,
            detected_by_agent_id=detected_by,
            affected_agent_id=affected,
            message=message,
            metadata={
                "auto_generated": True,
                "detection_time": datetime.utcnow().isoformat()
            }
        )
        
        # Determine who to notify based on severity
        notified = [agent.agentium_id]
        
        if severity in [ViolationSeverity.MAJOR, ViolationSeverity.CRITICAL]:
            # Notify Head of Council for major issues
            head = db.query(Agent).filter_by(agent_type=AgentType.HEAD_OF_COUNCIL).first()
            if head:
                notified.append(head.agentium_id)
        
        alert.notified_agents = notified
        db.add(alert)
        db.commit()