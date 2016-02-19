from troposphere import Base64, FindInMap, GetAtt, Join
from troposphere import Parameter, Output, Ref, Template
from troposphere.ec2 import SecurityGroupRule, SecurityGroup, NetworkInterfaceProperty, EIP, EIPAssociation
from troposphere.iam import LoginProfile, Policy, User, AccessKey
import troposphere.ec2 as ec2
from troposphere.cloudformation import WaitConditionHandle, WaitCondition
import awacs
import awacs.aws

template = Template()

keyname_param = template.add_parameter(Parameter(
    'KeyName',
    Description='Name of an existing EC2 KeyPair to enable SSH access to the instances',
    Type = 'AWS::EC2::KeyPair::KeyName'
))

vpcid_param = template.add_parameter(Parameter(
    'VpcId',
    Type = 'AWS::EC2::VPC::Id'
))

subnetid_param = template.add_parameter(Parameter(
    'SubnetId',
     Type = 'AWS::EC2::Subnet::Id'
))

template.add_mapping('RegionMap', {
    'us-east-1': {'AMI': 'ami-1ecae776'},
    'us-west-1': {'AMI': 'ami-d114f295'},
    'us-west-2': {'AMI': 'ami-e7527ed7'}
})

template.add_resource(User(
    'CfnUser',
    Path='/',
    Policies=[
        Policy(
            PolicyName='Admin',
            PolicyDocument=awacs.aws.Policy(
                Statement=[
                    awacs.aws.Statement(
                        Effect=awacs.aws.Allow,
                        Action=[awacs.aws.Action('*')],
                        Resource=['*']
                    )
                ]
            )
        )
    ]
))

HostKeys= template.add_resource(AccessKey(
        'HostKeys',    
        UserName=Ref('CfnUser')
))

waithandle= template.add_resource(WaitConditionHandle(
        'WaitHandle'
))

waitcondition= template.add_resource(WaitCondition(
        'WaitCondition',
        DependsOn = 'WebServer',
        Handle=Ref('WaitHandle'),
        Timeout='1200'
))

ipaddress = template.add_resource(EIP(
        'IPAddress'
))

ipassoc = template.add_resource(EIPAssociation(
        'IPAssoc',
        InstanceId = Ref('WebServer'),
        EIP = Ref('IPAddress')
))

sg_jenkins_web = template.add_resource(SecurityGroup(
    'InstanceSecurityGroup',
    VpcId=Ref('VpcId'),
    GroupDescription='Enable SSH access via port 22',
    SecurityGroupIngress=[
        SecurityGroupRule(
            IpProtocol='tcp',
            FromPort='22',
            ToPort='22',
            CidrIp='0.0.0.0/0'),
        SecurityGroupRule(
            IpProtocol='tcp',
            FromPort='80',
            ToPort='80',
            CidrIp='0.0.0.0/0'),
        SecurityGroupRule(
            IpProtocol='tcp',
            FromPort='8080',
            ToPort='8080',
            CidrIp='0.0.0.0/0')]
))

ec2_instance = template.add_resource(ec2.Instance(
    'WebServer',
    ImageId=FindInMap('RegionMap', Ref('AWS::Region'), 'AMI'),
    InstanceType='m3.large',
    KeyName=Ref(keyname_param),
    NetworkInterfaces=[
    NetworkInterfaceProperty(
        GroupSet=[
            Ref(sg_jenkins_web)],
        AssociatePublicIpAddress='true',
        DeviceIndex='0',
        DeleteOnTermination='true',
        SubnetId=Ref('SubnetId'))],
        UserData=Base64(
            Join(
                '',
                [
          '#!/bin/bash -v\n',
          'date > /home/ec2-user/starttime\n',

          '# Install packages\n',
          '/opt/aws/bin/cfn-init -s ', Ref('AWS::StackName'), ' -r WebServer',
          '    --access-key ',  Ref('HostKeys'),
          '    --secret-key ', GetAtt('HostKeys', 'SecretAccessKey'),
          '    --region ', Ref('AWS::Region'), '\n',

                    '# Install Jenkins\n',
                    'wget -O /etc/yum.repos.d/jenkins.repo http://pkg.jenkins-ci.org/redhat-stable/jenkins.repo\n',
                    'rpm --import https://jenkins-ci.org/redhat/jenkins-ci.org.key\n',
                    'yum -y install jenkins\n',

          '# Install Jenkins Plugins\n',
                    'wget -P /var/lib/jenkins/plugins/ http://updates.jenkins-ci.org/latest/git-client.hpi\n',
                    'wget -P /var/lib/jenkins/plugins/ http://updates.jenkins-ci.org/latest/scm-api.hpi\n',
                    'wget -P /var/lib/jenkins/plugins/ http://updates.jenkins-ci.org/latest/credentials.hpi\n',
          'wget -P /var/lib/jenkins/plugins/ http://updates.jenkins-ci.org/latest/git.hpi\n',
          'wget -P /var/lib/jenkins/plugins/ http://updates.jenkins-ci.org/latest/s3.hpi\n',
          'wget -P /var/lib/jenkins/plugins/ http://updates.jenkins-ci.org/latest/jenkins-cloudformation-plugin.hpi\n',
          'wget -P /var/lib/jenkins/plugins/ http://updates.jenkins-ci.org/latest/build-pipeline-plugin.hpi\n',
          'wget -P /var/lib/jenkins/plugins/ http://updates.jenkins-ci.org/latest/github.hpi\n',
          'wget -P /var/lib/jenkins/plugins/ http://updates.jenkins-ci.org/latest/dashboard-view.hpi\n',

                    'chown -R jenkins ../../var/lib/jenkins\n',
          'service jenkins start\n',
                    'chkconfig jenkins on\n',

          '/opt/aws/bin/cfn-signal', ' -e 0', " '", Ref('WaitHandle'), "'",'\n',

          'date > /home/ec2-user/stoptime'
                ])
        ),
))

template.add_output([
    Output(
        'InstanceIPAddress',
        Value=Ref('WebServer')
    ),
    Output(
        'JenkinsURL',
        Description='URL for newly created Jenkins app',
        Value=Join('',["http://", Ref('IPAddress'), ":8080"])
    )
])

print(template.to_json())
fileout = open('JenkinsTemplate.template', 'wb')
fileout.write(template.to_json());
fileout.close()